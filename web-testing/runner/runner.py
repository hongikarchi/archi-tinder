"""
runner.py -- Playwright E2E test orchestration.
Runs a full user scenario: dev-login -> create project -> search -> swipe -> results -> report.

Matches the actual frontend UI flow as of 2026-04-05:
  SetupPage (/) -> ProjectSetupPage (/new) -> LLMSearchPage (/search) ->
  SwipePage (/swipe) -> FavoritesPage (/library/{id})
"""
import json
import logging
import os
import time
from typing import List, Optional

from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeout

from .collector import Collector, StepRecord, ErrorRecord

# -- Constants --

FRONTEND_URL = 'http://localhost:5174'
BACKEND_URL = 'http://localhost:8001'
DEV_LOGIN_ENDPOINT = f'{BACKEND_URL}/api/v1/auth/dev-login/'

logger = logging.getLogger('web-testing.runner')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')


def _read_dev_login_secret() -> Optional[str]:
    """Read DEV_LOGIN_SECRET from backend/.env file."""
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'backend', '.env',
    )
    if not os.path.exists(env_path):
        logger.warning('backend/.env not found at %s', env_path)
        return None
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith('DEV_LOGIN_SECRET='):
                value = line.split('=', 1)[1].strip().strip('"').strip("'")
                return value if value else None
    logger.warning('DEV_LOGIN_SECRET not found in backend/.env')
    return None


def _dev_login(page: Page) -> Optional[dict]:
    """
    Authenticate via dev-login endpoint.
    Returns user data dict or None if dev-login is unavailable.
    """
    secret = _read_dev_login_secret()
    if not secret:
        logger.error('No DEV_LOGIN_SECRET available -- cannot authenticate')
        return None

    try:
        response = page.request.post(DEV_LOGIN_ENDPOINT, data={'secret': secret})
        if response.status != 200:
            logger.error('Dev-login returned status %d: %s', response.status, response.text())
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
            localStorage.setItem('archithon_tutorial_dismissed', 'true');
        }}""")

        logger.info('Dev-login successful for user_id=%s', user_id)
        return data
    except Exception as e:
        logger.error('Dev-login failed with exception: %s', e)
        return None


def _safe_click(page: Page, selector: str, description: str, timeout_ms: int = 5000) -> bool:
    """
    Click an element by selector. Returns True on success, False on failure.
    Logs the outcome either way -- never silently swallows errors.
    """
    try:
        el = page.locator(selector)
        el.first.wait_for(state='visible', timeout=timeout_ms)
        el.first.click()
        logger.info('Clicked: %s (selector: %s)', description, selector)
        return True
    except PlaywrightTimeout:
        logger.error('Timeout waiting for "%s" (selector: %s, %dms)', description, selector, timeout_ms)
        return False
    except Exception as e:
        logger.error('Failed to click "%s" (selector: %s): %s', description, selector, e)
        return False


def _safe_fill(page: Page, selector: str, value: str, description: str, timeout_ms: int = 5000) -> bool:
    """Fill an input element. Returns True on success."""
    try:
        el = page.locator(selector)
        el.first.wait_for(state='visible', timeout=timeout_ms)
        el.first.fill(value)
        logger.info('Filled "%s" with "%s"', description, value[:50])
        return True
    except PlaywrightTimeout:
        logger.error('Timeout waiting for "%s" (selector: %s)', description, selector)
        return False
    except Exception as e:
        logger.error('Failed to fill "%s": %s', description, e)
        return False


def _extract_card_metadata(page: Page) -> dict:
    """
    Extract building card metadata from the currently visible swipe card.
    The card shows: h2 (title), and InfoRow components with label/value pairs.
    The card details are only visible when the card is in "expanded" state (tap to expand).
    We tap the card first to expand it, extract metadata, then tap again to collapse.
    """
    try:
        metadata = page.evaluate("""() => {
            const result = {
                building_id: '',
                title: '',
                axis_typology: '',
                axis_style: '',
                axis_atmosphere: '',
                axis_material: '',
                axis_material_visual: [],
            };

            // Card title is in an h2 inside the card
            const h2 = document.querySelector('h2');
            if (h2) result.title = h2.textContent.trim();

            // InfoRow components render as pairs:
            //   div > div (label, uppercase, small) + div (value)
            // Labels are: Type, Country, Year, Area, Style, Atmosphere, Material
            const allDivs = document.querySelectorAll('div');
            for (const div of allDivs) {
                const children = div.children;
                if (children.length === 2) {
                    const labelEl = children[0];
                    const valueEl = children[1];
                    const labelText = labelEl.textContent.trim().toLowerCase();
                    const valueText = valueEl.textContent.trim();
                    if (labelText === 'type' && valueText) result.axis_typology = valueText;
                    if (labelText === 'style' && valueText) result.axis_style = valueText;
                    if (labelText === 'atmosphere' && valueText) result.axis_atmosphere = valueText;
                    if (labelText === 'material' && valueText) result.axis_material = valueText;
                }
            }

            return result;
        }""")
        return metadata or {}
    except Exception as e:
        logger.warning('Failed to extract card metadata: %s', e)
        return {}


def run_test(scenario, run_id: str, reports_dir: str) -> List[StepRecord]:
    """
    Execute a full E2E test scenario using Playwright.

    Follows the actual frontend flow:
    1. Dev-login (inject JWT tokens)
    2. Home page -- click "Create new folder"
    3. Project setup -- fill name, click "Go to AI Search"
    4. LLM Search -- type query or click preset, wait for results, click "Start swiping"
    5. Swipe page -- use Like/Dislike buttons (aria-label), detect action card
    6. View results -- navigate to library
    7. Generate persona report

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

        # Attach listeners for API call and error tracking
        collector.start_tracking_responses(page)
        collector.start_tracking_console(page)
        collector.start_tracking_exceptions(page)

        # ================================================================
        # Step 1: Dev Login
        # ================================================================
        t0 = time.time()
        logger.info('Step 1: Navigating to %s for dev-login', FRONTEND_URL)
        page.goto(FRONTEND_URL, wait_until='domcontentloaded')
        page.wait_for_timeout(1000)

        login_data = _dev_login(page)
        if login_data:
            page.reload(wait_until='domcontentloaded')
            page.wait_for_timeout(2000)
            step = collector.collect_step(page, '01_dev_login', t0, {
                'authenticated': True,
                'user_id': login_data.get('user', {}).get('user_id'),
            })
        else:
            page.wait_for_timeout(1000)
            step = collector.collect_step(page, '01_dev_login', t0, {
                'authenticated': False,
                'reason': 'DEV_LOGIN_SECRET not available',
            })
        steps.append(step)

        if not login_data:
            logger.error('Cannot proceed without authentication -- aborting')
            t0 = time.time()
            step = collector.collect_step(page, '02_unauthenticated_abort', t0)
            steps.append(step)
            browser.close()
            return steps

        # ================================================================
        # Step 2: Home Page -- Click "Create new folder"
        # ================================================================
        t0 = time.time()
        logger.info('Step 2: Home page -- looking for "Create new folder"')

        # Wait for the SetupPage to render with the "Create new folder" button
        create_found = False
        try:
            page.get_by_text('Create new folder').wait_for(state='visible', timeout=10000)
            create_found = True
        except PlaywrightTimeout:
            logger.error('Home page: "Create new folder" button not found within 10s')

        step = collector.collect_step(page, '02_home', t0, {
            'create_new_folder_visible': create_found,
            'url': page.url,
        })
        steps.append(step)

        if not create_found:
            logger.error('Cannot proceed without "Create new folder" button -- aborting')
            step.errors.append(ErrorRecord(
                message='Home page missing "Create new folder" button',
                source='assertion',
            ))
            browser.close()
            return steps

        # Click "Create new folder"
        page.get_by_text('Create new folder').click()
        logger.info('Clicked "Create new folder"')

        # Wait for navigation to /new
        try:
            page.wait_for_url('**/new', timeout=5000)
            logger.info('Navigated to /new')
        except PlaywrightTimeout:
            logger.error('Navigation to /new failed after clicking "Create new folder"')

        # ================================================================
        # Step 3: Project Setup -- Fill name, click "Go to AI Search"
        # ================================================================
        t0 = time.time()
        logger.info('Step 3: Project setup page')

        project_name = f"Test - {scenario.persona.name}"

        # Fill the project name input (the only text input on this page)
        name_filled = _safe_fill(
            page, 'input[type="text"]', project_name,
            'project name input', timeout_ms=5000,
        )

        if not name_filled:
            step = collector.collect_step(page, '03_project_setup', t0, {
                'error': 'Could not find or fill project name input',
                'url': page.url,
            })
            step.errors.append(ErrorRecord(
                message='Project name input not found on /new page',
                source='assertion',
            ))
            steps.append(step)
            browser.close()
            return steps

        page.wait_for_timeout(300)

        # Click "Go to AI Search" button
        go_to_search = _safe_click(
            page, 'text=Go to AI Search', '"Go to AI Search" button', timeout_ms=5000,
        )

        step = collector.collect_step(page, '03_project_setup', t0, {
            'project_name': project_name,
            'name_filled': name_filled,
            'go_to_search_clicked': go_to_search,
            'url': page.url,
        })
        steps.append(step)

        if not go_to_search:
            step.errors.append(ErrorRecord(
                message='"Go to AI Search" button not found or not clickable',
                source='assertion',
            ))
            browser.close()
            return steps

        # Wait for navigation to /search
        try:
            page.wait_for_url('**/search**', timeout=5000)
            logger.info('Navigated to /search')
        except PlaywrightTimeout:
            logger.error('Navigation to /search failed')

        # ================================================================
        # Step 4: LLM Search -- Submit query, wait for results
        # ================================================================
        t0 = time.time()
        logger.info('Step 4: LLM search page -- query: "%s"', scenario.search_query)

        page.wait_for_timeout(1000)

        # The search page has:
        #   - Preset buttons (shown before first user message)
        #   - Input with placeholder "Find a modern museum in Japan..."
        #   - Submit button (pink circle with SVG arrow)
        search_submitted = False

        # Try using the text input first
        search_input = page.locator('input[placeholder*="Find a modern"]')
        try:
            search_input.wait_for(state='visible', timeout=3000)
            search_input.fill(scenario.search_query)
            page.wait_for_timeout(200)

            # Click the submit button (type="submit" inside the form)
            submit_btn = page.locator('button[type="submit"]')
            if submit_btn.first.is_visible(timeout=1000):
                submit_btn.first.click()
                search_submitted = True
                logger.info('Submitted search query via input + submit button')
        except PlaywrightTimeout:
            logger.warning('Search input not found, trying preset buttons')

        # Fallback: click a preset button
        if not search_submitted:
            presets = [
                'Japanese modern museum', 'Minimalist housing',
                'Landscape architecture', 'Brutalist office',
                'Religious architecture', 'Boutique hospitality',
            ]
            for preset_text in presets:
                try:
                    preset_btn = page.get_by_text(preset_text, exact=True)
                    if preset_btn.is_visible(timeout=1000):
                        preset_btn.click()
                        search_submitted = True
                        logger.info('Clicked preset button: "%s"', preset_text)
                        break
                except Exception:
                    continue

        if not search_submitted:
            logger.error('Could not submit search query or click any preset')

        step = collector.collect_step(page, '04_search_submitted', t0, {
            'query': scenario.search_query,
            'search_submitted': search_submitted,
            'url': page.url,
        })
        if not search_submitted:
            step.errors.append(ErrorRecord(
                message='Failed to submit search query or click preset',
                source='assertion',
            ))
        steps.append(step)

        if not search_submitted:
            browser.close()
            return steps

        # ================================================================
        # Step 5: Wait for search results + "Start swiping" button
        # ================================================================
        t0 = time.time()
        logger.info('Step 5: Waiting for "Start swiping" button (LLM + search may take 10-30s)')

        start_swiping_found = False
        try:
            # The button text is "Start swiping - {count}" or "Update with these results - {count}"
            start_btn = page.locator('button').filter(has_text='swiping')
            start_btn.first.wait_for(state='visible', timeout=30000)
            start_swiping_found = True
            logger.info('"Start swiping" button appeared')
        except PlaywrightTimeout:
            logger.error('"Start swiping" button did not appear within 30s')
            # Check if there's an error message
            try:
                error_text = page.locator('text=Something went wrong').first
                if error_text.is_visible(timeout=500):
                    logger.error('Search returned error: "Something went wrong"')
            except Exception:
                pass

        step = collector.collect_step(page, '05_search_results', t0, {
            'start_swiping_visible': start_swiping_found,
            'url': page.url,
        })
        if not start_swiping_found:
            step.errors.append(ErrorRecord(
                message='"Start swiping" button not found after search',
                source='assertion',
            ))
        steps.append(step)

        if not start_swiping_found:
            browser.close()
            return steps

        # Click "Start swiping"
        start_btn = page.locator('button').filter(has_text='swiping')
        start_btn.first.click()
        logger.info('Clicked "Start swiping"')

        # Wait for navigation to /swipe
        try:
            page.wait_for_url('**/swipe', timeout=10000)
            logger.info('Navigated to /swipe')
        except PlaywrightTimeout:
            logger.error('Navigation to /swipe failed after clicking "Start swiping"')

        # Wait for card to load
        page.wait_for_timeout(3000)

        # ================================================================
        # Step 6: Swipe Loop
        # ================================================================
        swipe_count = 0
        likes = 0
        dislikes = 0
        buildings_liked: List[str] = []
        session_completed = False

        # Take initial swipe page screenshot
        t0 = time.time()
        step = collector.collect_step(page, '06_swipe_start', t0, {
            'url': page.url,
        })
        steps.append(step)

        for i in range(scenario.max_swipes):
            t0 = time.time()

            # Check for action card (convergence): "Your Taste is Found!"
            try:
                action_card = page.locator('text=Your Taste is Found')
                if action_card.first.is_visible(timeout=800):
                    logger.info('Action card detected: "Your Taste is Found!" after %d swipes', swipe_count)
                    session_completed = True

                    step = collector.collect_step(page, f'07_swipe_{i+1:02d}_action_card', t0, {
                        'action': 'action_card_detected',
                        'total_swipes': swipe_count,
                        'total_likes': likes,
                        'total_dislikes': dislikes,
                    })
                    steps.append(step)

                    # Swipe right on the action card to accept results
                    like_btn = page.locator('button[aria-label="Like"]')
                    try:
                        like_btn.wait_for(state='visible', timeout=2000)
                        like_btn.click()
                        logger.info('Swiped right on action card to view results')
                        page.wait_for_timeout(2000)
                    except PlaywrightTimeout:
                        logger.warning('Like button not visible on action card, trying "View Results" button')
                        _safe_click(page, 'text=View Results', '"View Results" button', timeout_ms=3000)
                        page.wait_for_timeout(2000)
                    break
            except Exception:
                pass

            # Check for "View Results" button (converged/completed phase)
            try:
                view_results_btn = page.get_by_text('View Results', exact=False)
                if view_results_btn.is_visible(timeout=300):
                    logger.info('"View Results" button visible -- session converged')
                    session_completed = True
                    view_results_btn.click()
                    page.wait_for_timeout(2000)

                    step = collector.collect_step(page, f'07_swipe_{i+1:02d}_view_results', t0, {
                        'action': 'view_results_clicked',
                        'total_swipes': swipe_count,
                    })
                    steps.append(step)
                    break
            except Exception:
                pass

            # Check if there's a card visible (the like/dislike buttons exist when card is present)
            like_btn = page.locator('button[aria-label="Like"]')
            dislike_btn = page.locator('button[aria-label="Dislike"]')

            try:
                like_btn.wait_for(state='visible', timeout=3000)
            except PlaywrightTimeout:
                logger.warning('Like button not visible -- no card loaded? Swipe %d', i + 1)
                step = collector.collect_step(page, f'07_swipe_{i+1:02d}_no_card', t0, {
                    'error': 'Like button not visible -- no card available',
                    'swipe_number': swipe_count + 1,
                })
                step.errors.append(ErrorRecord(
                    message=f'Swipe {i+1}: Like button not visible, card may not have loaded',
                    source='assertion',
                ))
                steps.append(step)
                break

            # Try to tap the card to expand details for metadata extraction
            try:
                # The card is inside a TinderCard wrapper. Tap it to expand.
                card_area = page.locator('h1').first  # The project name heading is always visible
                # Actually, just try to extract whatever is visible
                pass
            except Exception:
                pass

            # Extract card metadata from the visible card
            card_metadata = _extract_card_metadata(page)
            building_id = card_metadata.get('building_id', '')
            card_title = card_metadata.get('title', '')

            # Decide swipe direction based on persona preferences
            decision = scenario.decide_swipe(card_metadata, scenario.persona)

            # Execute swipe via buttons (NOT mouse drag)
            if decision == 'like':
                like_btn.click()
                likes += 1
                if building_id:
                    buildings_liked.append(building_id)
                logger.info('Swipe %d: LIKE (title: "%s")', swipe_count + 1, card_title[:40])
            else:
                dislike_btn.click()
                dislikes += 1
                logger.info('Swipe %d: DISLIKE (title: "%s")', swipe_count + 1, card_title[:40])

            swipe_count += 1

            # Wait for swipe animation + next card to load
            page.wait_for_timeout(1500)

            # Capture screenshot every 3rd swipe to avoid too many screenshots
            if swipe_count % 3 == 1 or swipe_count <= 2:
                step = collector.collect_step(page, f'07_swipe_{i+1:02d}', t0, {
                    'swipe_number': swipe_count,
                    'decision': decision,
                    'building_id': building_id,
                    'card_title': card_title,
                    'card_program': card_metadata.get('axis_typology', ''),
                    'card_style': card_metadata.get('axis_style', ''),
                })
                steps.append(step)

        # ================================================================
        # Step 7: View Results / Navigate to Library
        # ================================================================
        t0 = time.time()
        logger.info('Step 7: Attempting to view results (swipes=%d, likes=%d)', swipe_count, likes)

        if not session_completed:
            # Session didn't converge naturally. Check if we can still view results.
            try:
                view_btn = page.get_by_text('View Results', exact=False)
                if view_btn.is_visible(timeout=2000):
                    view_btn.click()
                    page.wait_for_timeout(2000)
                    session_completed = True
                    logger.info('Clicked "View Results" post-swipe-loop')
            except Exception:
                pass

            if not session_completed:
                # Try "View Image Board" (shown on completed state)
                try:
                    board_btn = page.get_by_text('View Image Board', exact=False)
                    if board_btn.is_visible(timeout=2000):
                        board_btn.click()
                        page.wait_for_timeout(2000)
                        session_completed = True
                        logger.info('Clicked "View Image Board"')
                except Exception:
                    pass

        # If still not on library, try navigating via tab bar
        if '/library' not in page.url:
            try:
                # Library tab is the 3rd tab (index 2) in the tab bar
                library_tab = page.locator('nav button').nth(2)
                if library_tab.is_visible(timeout=2000):
                    library_tab.click()
                    page.wait_for_timeout(1500)
                    logger.info('Navigated to library via tab bar')
            except Exception as e:
                logger.warning('Could not navigate to library via tab: %s', e)

        step = collector.collect_step(page, '08_results', t0, {
            'total_swipes': swipe_count,
            'likes': likes,
            'dislikes': dislikes,
            'buildings_liked': buildings_liked,
            'session_completed': session_completed,
            'url': page.url,
        })
        steps.append(step)

        # ================================================================
        # Step 8: Generate Persona Report
        # ================================================================
        if scenario.generate_report and likes > 0:
            t0 = time.time()
            logger.info('Step 8: Attempting to generate persona report')

            report_generated = False

            # Look for "Generate Persona Report" button on library/favorites page
            try:
                report_btn = page.get_by_text('Generate Persona Report', exact=False)
                if report_btn.is_visible(timeout=5000):
                    report_btn.click()
                    logger.info('Clicked "Generate Persona Report" -- waiting for Gemini (up to 30s)')

                    # Wait for report to generate (Gemini API can take 15-30s)
                    page.wait_for_timeout(20000)

                    # Check if report content appeared (persona type text)
                    try:
                        # The report shows persona type, description, etc.
                        persona_type = page.locator('text=Persona Type').first
                        if persona_type.is_visible(timeout=10000):
                            report_generated = True
                            logger.info('Persona report generated successfully')
                    except PlaywrightTimeout:
                        logger.warning('Persona report content did not appear within timeout')

                    step = collector.collect_step(page, '09_persona_report', t0, {
                        'report_generated': report_generated,
                        'url': page.url,
                    })
                else:
                    logger.warning('"Generate Persona Report" button not visible')
                    step = collector.collect_step(page, '09_persona_report', t0, {
                        'report_generated': False,
                        'reason': 'Generate button not found',
                        'url': page.url,
                    })
            except Exception as e:
                logger.error('Persona report step failed: %s', e)
                step = collector.collect_step(page, '09_persona_report', t0, {
                    'report_generated': False,
                    'error': str(e),
                    'url': page.url,
                })
                step.errors.append(ErrorRecord(
                    message=f'Persona report generation failed: {e}',
                    source='exception',
                ))
            steps.append(step)

        # ================================================================
        # Step 9: Final State
        # ================================================================
        t0 = time.time()
        step = collector.collect_step(page, '10_final_state', t0, {
            'total_steps': len(steps) + 1,
            'total_swipes': swipe_count,
            'total_likes': likes,
            'total_dislikes': dislikes,
            'buildings_liked': buildings_liked,
            'session_completed': session_completed,
            'final_url': page.url,
        })
        steps.append(step)

        logger.info(
            'Test complete: %d steps, %d swipes (%d likes, %d dislikes), completed=%s',
            len(steps), swipe_count, likes, dislikes, session_completed,
        )

        browser.close()

    return steps
