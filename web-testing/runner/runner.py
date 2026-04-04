"""
runner.py -- Playwright E2E test orchestration.
Runs a full user scenario: dev-login -> search -> swipe -> results -> report.
"""
import json
import os
import time
from typing import List, Optional

from playwright.sync_api import sync_playwright, Page

from .collector import Collector, StepRecord, ErrorRecord

# -- Constants --

FRONTEND_URL = 'http://localhost:5173'
BACKEND_URL = 'http://localhost:8001'
DEV_LOGIN_ENDPOINT = f'{BACKEND_URL}/api/v1/auth/dev-login/'


def _read_dev_login_secret() -> Optional[str]:
    """Read DEV_LOGIN_SECRET from backend/.env file."""
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'backend', '.env',
    )
    if not os.path.exists(env_path):
        return None
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith('DEV_LOGIN_SECRET='):
                value = line.split('=', 1)[1].strip().strip('"').strip("'")
                return value if value else None
    return None


def _dev_login(page: Page) -> Optional[dict]:
    """
    Authenticate via dev-login endpoint.
    Returns user data dict or None if dev-login is unavailable.
    """
    secret = _read_dev_login_secret()
    if not secret:
        return None

    try:
        response = page.request.post(DEV_LOGIN_ENDPOINT, data={'secret': secret})
        if response.status != 200:
            return None
        data = response.json()
        access = data.get('access', '')
        refresh = data.get('refresh', '')
        user = data.get('user', {})
        user_id = str(user.get('user_id', ''))

        # Inject tokens into browser
        page.evaluate(f"""() => {{
            localStorage.setItem('archithon_access', '{access}');
            localStorage.setItem('archithon_refresh', '{refresh}');
            sessionStorage.setItem('archithon_user', '{user_id}');
            localStorage.setItem('__debugMode', 'true');
        }}""")

        return data
    except Exception:
        return None


def _wait_for_app_ready(page: Page, timeout_ms: int = 10000):
    """Wait for the React app to be mounted and ready."""
    try:
        page.wait_for_selector('[data-testid], nav, .tab-bar, button', timeout=timeout_ms)
    except Exception:
        # Fallback: just wait for network idle
        try:
            page.wait_for_load_state('networkidle', timeout=timeout_ms)
        except Exception:
            pass


def _navigate_to_swipe(page: Page):
    """Navigate to the swipe page via the tab bar."""
    try:
        # Look for the swipe/discover tab -- typically the middle tab
        swipe_tab = page.locator('nav button, nav a').nth(1)
        if swipe_tab.is_visible():
            swipe_tab.click()
            page.wait_for_timeout(1000)
    except Exception:
        # Fallback: direct navigation
        page.goto(f'{FRONTEND_URL}/swipe')
        page.wait_for_timeout(1000)


def _navigate_to_favorites(page: Page):
    """Navigate to the favorites page via the tab bar."""
    try:
        fav_tab = page.locator('nav button, nav a').nth(2)
        if fav_tab.is_visible():
            fav_tab.click()
            page.wait_for_timeout(1000)
    except Exception:
        page.goto(f'{FRONTEND_URL}/favorites')
        page.wait_for_timeout(1000)


def run_test(scenario, run_id: str, reports_dir: str) -> List[StepRecord]:
    """
    Execute a full E2E test scenario using Playwright.

    Args:
        scenario: TestScenario instance with persona, search_query, decide_swipe, etc.
        run_id: Unique identifier for this test run.
        reports_dir: Directory to store reports and screenshots.

    Returns:
        List of StepRecord objects documenting each test step.
    """
    run_dir = os.path.join(reports_dir, run_id)
    os.makedirs(run_dir, exist_ok=True)

    collector = Collector(run_id=run_id, base_dir=run_dir)
    steps: List[StepRecord] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 390, 'height': 844},  # iPhone 14 Pro
            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
        )
        page = context.new_page()

        # Attach listeners
        collector.start_tracking_responses(page)
        collector.start_tracking_console(page)
        collector.start_tracking_exceptions(page)

        # -- Step 1: Dev Login --
        t0 = time.time()
        page.goto(FRONTEND_URL)
        page.wait_for_timeout(1000)
        login_data = _dev_login(page)

        if login_data:
            page.reload()
            _wait_for_app_ready(page)
            step = collector.collect_step(page, '01_dev_login', t0, {
                'authenticated': True,
                'user_id': login_data.get('user', {}).get('user_id'),
            })
        else:
            _wait_for_app_ready(page)
            step = collector.collect_step(page, '01_dev_login', t0, {
                'authenticated': False,
                'reason': 'DEV_LOGIN_SECRET not available',
            })
        steps.append(step)

        if not login_data:
            # Cannot proceed without auth -- capture home and return
            t0 = time.time()
            step = collector.collect_step(page, '02_home_unauthenticated', t0)
            steps.append(step)
            browser.close()
            return steps

        # -- Step 2: Home Screenshot --
        t0 = time.time()
        page.wait_for_timeout(500)
        step = collector.collect_step(page, '02_home', t0)
        steps.append(step)

        # -- Step 3: LLM Search --
        t0 = time.time()
        try:
            # Navigate to home/search page
            home_tab = page.locator('nav button, nav a').first
            if home_tab.is_visible():
                home_tab.click()
                page.wait_for_timeout(500)

            # Find the search input
            search_input = page.locator('input[type="text"], textarea').first
            if search_input.is_visible(timeout=3000):
                search_input.fill(scenario.search_query)
                page.wait_for_timeout(300)

                # Submit search (look for submit button or press Enter)
                submit_btn = page.locator('button[type="submit"], form button').first
                if submit_btn.is_visible(timeout=1000):
                    submit_btn.click()
                else:
                    search_input.press('Enter')

                # Wait for search results
                page.wait_for_timeout(3000)

            step = collector.collect_step(page, '03_llm_search', t0, {
                'query': scenario.search_query,
            })
        except Exception as e:
            step = collector.collect_step(page, '03_llm_search', t0, {
                'query': scenario.search_query,
                'error': str(e),
            })
            step.errors.append(ErrorRecord(
                message=f"LLM search failed: {e}",
                source='exception',
            ))
        steps.append(step)

        # -- Step 4: Start Swiping --
        t0 = time.time()
        try:
            # Look for "Start Swiping" or similar button
            start_btn = page.locator('button:has-text("Start"), button:has-text("swip")')
            if start_btn.first.is_visible(timeout=3000):
                start_btn.first.click()
                page.wait_for_timeout(2000)

            step = collector.collect_step(page, '04_swipe_start', t0)
        except Exception as e:
            step = collector.collect_step(page, '04_swipe_start', t0, {
                'error': str(e),
            })
        steps.append(step)

        # -- Step 5: Swiping Loop --
        swipe_count = 0
        likes = 0
        dislikes = 0
        buildings_liked: List[str] = []
        session_completed = False

        for i in range(scenario.max_swipes):
            t0 = time.time()
            try:
                # Check for action card (session convergence)
                action_card = page.locator('text=Your Taste is Found, text=Analysis Complete, text=View Results')
                if action_card.first.is_visible(timeout=500):
                    # Session has converged -- click "View Results"
                    view_btn = page.locator('button:has-text("View"), button:has-text("result")')
                    if view_btn.first.is_visible(timeout=1000):
                        view_btn.first.click()
                        page.wait_for_timeout(2000)
                    session_completed = True
                    step = collector.collect_step(page, f'05_swipe_{i+1:02d}_action_card', t0, {
                        'action': 'view_results',
                        'total_swipes': swipe_count,
                    })
                    steps.append(step)
                    break

                # Get card metadata from the page
                card_metadata = _extract_card_metadata(page)
                building_id = card_metadata.get('building_id', '')

                # Decide swipe direction
                decision = scenario.decide_swipe(card_metadata, scenario.persona)

                # Execute swipe gesture
                if decision == 'like':
                    _swipe_right(page)
                    likes += 1
                    if building_id:
                        buildings_liked.append(building_id)
                else:
                    _swipe_left(page)
                    dislikes += 1

                swipe_count += 1
                page.wait_for_timeout(800)

                step = collector.collect_step(page, f'05_swipe_{i+1:02d}', t0, {
                    'swipe_number': swipe_count,
                    'decision': decision,
                    'building_id': building_id,
                    'card_title': card_metadata.get('title', ''),
                    'card_program': card_metadata.get('axis_typology', ''),
                    'card_style': card_metadata.get('axis_style', ''),
                })
            except Exception as e:
                step = collector.collect_step(page, f'05_swipe_{i+1:02d}_error', t0, {
                    'error': str(e),
                    'swipe_number': swipe_count,
                })
                step.errors.append(ErrorRecord(
                    message=f"Swipe {i+1} failed: {e}",
                    source='exception',
                ))
            steps.append(step)

        # -- Step 6: View Results --
        t0 = time.time()
        if not session_completed:
            # Try to view results even if not converged
            try:
                view_btn = page.locator('button:has-text("View"), button:has-text("result")')
                if view_btn.first.is_visible(timeout=2000):
                    view_btn.first.click()
                    page.wait_for_timeout(2000)
            except Exception:
                pass

        step = collector.collect_step(page, '06_results', t0, {
            'total_swipes': swipe_count,
            'likes': likes,
            'dislikes': dislikes,
            'buildings_liked': buildings_liked,
            'session_completed': session_completed,
        })
        steps.append(step)

        # -- Step 7: Navigate to Favorites & Generate Report --
        if scenario.generate_report and likes > 0:
            t0 = time.time()
            try:
                _navigate_to_favorites(page)
                page.wait_for_timeout(1000)

                # Look for generate report button
                report_btn = page.locator('button:has-text("Generate"), button:has-text("Persona")')
                if report_btn.first.is_visible(timeout=3000):
                    report_btn.first.click()
                    # Wait for report generation (can take a while due to Gemini)
                    page.wait_for_timeout(8000)

                step = collector.collect_step(page, '07_persona_report', t0, {
                    'report_generated': True,
                })
            except Exception as e:
                step = collector.collect_step(page, '07_persona_report', t0, {
                    'report_generated': False,
                    'error': str(e),
                })
            steps.append(step)

        # -- Step 8: Final State --
        t0 = time.time()
        step = collector.collect_step(page, '08_final_state', t0, {
            'total_steps': len(steps) + 1,
            'total_swipes': swipe_count,
            'total_likes': likes,
            'total_dislikes': dislikes,
        })
        steps.append(step)

        browser.close()

    return steps


def _extract_card_metadata(page: Page) -> dict:
    """
    Extract building card metadata from the current page.
    Returns a dict with building info readable by decide_swipe.
    """
    try:
        metadata = page.evaluate("""() => {
            // Try to extract from debug overlay or data attributes
            const card = document.querySelector('[data-building-id]');
            if (card) {
                return {
                    building_id: card.dataset.buildingId || '',
                    title: card.dataset.title || '',
                    axis_typology: card.dataset.program || '',
                    axis_style: card.dataset.style || '',
                    axis_atmosphere: card.dataset.atmosphere || '',
                    axis_material: card.dataset.material || '',
                    axis_material_visual: [],
                };
            }

            // Fallback: try to get from visible text
            const titleEl = document.querySelector('h2, h3, .card-title');
            const title = titleEl ? titleEl.textContent : '';

            // Try to get metadata from card info section
            const metaEls = document.querySelectorAll('.metadata span, .card-info span');
            const metaTexts = Array.from(metaEls).map(el => el.textContent);

            return {
                building_id: '',
                title: title,
                axis_typology: metaTexts[0] || '',
                axis_style: '',
                axis_atmosphere: '',
                axis_material: '',
                axis_material_visual: [],
            };
        }""")
        return metadata or {}
    except Exception:
        return {}


def _swipe_right(page: Page):
    """Simulate a right swipe (like) gesture."""
    try:
        # Find the card element
        card = page.locator('.react-tinder-card, [class*="swipe"], [class*="card"]').first
        if card.is_visible(timeout=1000):
            box = card.bounding_box()
            if box:
                start_x = box['x'] + box['width'] / 2
                start_y = box['y'] + box['height'] / 2
                page.mouse.move(start_x, start_y)
                page.mouse.down()
                # Swipe right with enough distance
                for step in range(5):
                    page.mouse.move(start_x + (step + 1) * 40, start_y, steps=2)
                page.mouse.move(start_x + 250, start_y, steps=2)
                page.mouse.up()
                return

        # Fallback: keyboard shortcut or button
        like_btn = page.locator('button:has-text("Like"), button[aria-label="like"]')
        if like_btn.first.is_visible(timeout=500):
            like_btn.first.click()
    except Exception:
        pass


def _swipe_left(page: Page):
    """Simulate a left swipe (dislike) gesture."""
    try:
        card = page.locator('.react-tinder-card, [class*="swipe"], [class*="card"]').first
        if card.is_visible(timeout=1000):
            box = card.bounding_box()
            if box:
                start_x = box['x'] + box['width'] / 2
                start_y = box['y'] + box['height'] / 2
                page.mouse.move(start_x, start_y)
                page.mouse.down()
                for step in range(5):
                    page.mouse.move(start_x - (step + 1) * 40, start_y, steps=2)
                page.mouse.move(start_x - 250, start_y, steps=2)
                page.mouse.up()
                return

        dislike_btn = page.locator('button:has-text("Dislike"), button[aria-label="dislike"]')
        if dislike_btn.first.is_visible(timeout=500):
            dislike_btn.first.click()
    except Exception:
        pass
