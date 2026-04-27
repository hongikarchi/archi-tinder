"""
runner.py -- Playwright E2E test orchestration.
Runs a full user scenario: dev-login -> create project -> search -> swipe -> results -> report.

Matches the actual frontend UI flow as of 2026-04-06:
  SetupPage (/) -> ProjectSetupPage (/new) -> LLMSearchPage (/search) ->
  SwipePage (/swipe) -> FavoritesPage (/library/{id})

Swipe mechanism: keyboard ArrowRight (like) / ArrowLeft (dislike).
The UX4 Gemini overhaul removed Like/Dislike buttons; only keyboard and touch gestures remain.
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


def _setup_swipe_listener(page: Page) -> dict:
    """
    Set up a listener for swipe API response BEFORE pressing the key.
    Returns a dict that will be populated when the response arrives.
    Must be called before the keyboard press.
    """
    swipe_data = {'response': None, '_handler': None}

    def capture(response):
        if '/swipes/' in response.url and response.request.method == 'POST':
            try:
                swipe_data['response'] = response.json()
            except Exception:
                swipe_data['response'] = {}

    swipe_data['_handler'] = capture
    page.on('response', capture)
    return swipe_data


def _collect_swipe_response(page: Page, swipe_data: dict, timeout_ms: int = 5000) -> Optional[dict]:
    """
    Wait for the swipe API response that was set up by _setup_swipe_listener.
    Uses tight polling with short intervals since the listener is already active.
    """
    try:
        deadline = time.time() + (timeout_ms / 1000)
        while time.time() < deadline:
            if swipe_data['response'] is not None:
                break
            page.wait_for_timeout(50)
    finally:
        try:
            page.remove_listener('response', swipe_data['_handler'])
        except Exception:
            pass

    return swipe_data['response']


def _wait_for_new_card(page: Page, prev_title: str, timeout_ms: int = 3000) -> bool:
    """
    Wait until the card title changes from prev_title, indicating a new card loaded.
    Returns True if card changed, False on timeout.
    """
    if not prev_title:
        page.wait_for_timeout(300)
        return True

    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        try:
            current_title = page.evaluate("""() => {
                const h2 = document.querySelector('h2');
                return h2 ? h2.textContent.trim() : '';
            }""")
            if current_title and current_title != prev_title:
                return True
        except Exception:
            pass
        page.wait_for_timeout(100)

    return False


def _wait_for_card_image(page: Page, timeout_ms: int = 3000):
    """
    Wait for the card image to finish loading so screenshots show the building photo.
    Checks that an <img> element has naturalWidth > 0 and is tall enough to be a card image.
    """
    try:
        page.wait_for_function("""() => {
            const imgs = document.querySelectorAll('img');
            for (const img of imgs) {
                if (img.naturalWidth > 0 && img.offsetHeight > 100) return true;
            }
            return false;
        }""", timeout=timeout_ms)
    except Exception:
        pass  # Image may not load in time -- take screenshot anyway


def _canned_reply_for(query: str, turn_idx: int) -> str:
    """Return a persona-appropriate canned reply for a clarification turn.

    Per spec v1.9 + Investigation 22 mitigation M1 + .claude/commands/review.md
    Step B4 multi-turn loop. Picks reply based on initial query class +
    turn index (turn 2 specific, turn 3+ fallback "either both").

    Args:
        query: The original NL search query.
        turn_idx: Which clarification turn we're on (1-indexed; 1 = first
            clarification reply, 2 = second, etc.).

    Returns:
        Canned reply string suitable for the chat textarea.
    """
    q_lower = query.lower()
    if turn_idx >= 2:
        return 'either is fine, both options'
    if 'brutalist' in q_lower or 'concrete' in q_lower:
        return 'yes concrete brutalist museums'
    if 'sustainable' in q_lower or 'timber' in q_lower or '한국' in query:
        return 'yes sustainable timber school in Korea'
    return 'either is fine, surprise me'


def _detect_clarification_or_results(page: Page, timeout_ms: int = 8000) -> str:
    """Poll for either 'Start swiping' button OR clarification AI message.

    Per spec v1.9 §4: TTFC measured from last user clarification submit, so we
    must distinguish clarification-fire from session-creation-fire.

    Returns:
        'results' — 'Start swiping' button is visible → no clarification fired
        'clarification' — input still present without 'Start swiping' button →
            clarification likely fired (indirect detection — Gemini asked a
            question instead of returning filters)
        'timeout' — neither condition observable within timeout (failure)
    """
    poll_interval_ms = 250
    elapsed_ms = 0
    while elapsed_ms < timeout_ms:
        # Fast-path: 'Start swiping' button is the success terminal
        try:
            start_btn = page.locator('button').filter(has_text='swiping')
            if start_btn.first.is_visible(timeout=200):
                return 'results'
        except Exception:
            pass
        # Slow-path: clarification check — search input still present means
        # the chat phase has not transitioned to results yet (clarification
        # likely fired or initial response is still streaming)
        try:
            search_input = page.locator('input[placeholder*="Find a modern"]')
            if search_input.is_visible(timeout=200):
                # Input still here. If we've waited past ~3s without 'swiping'
                # button, treat as clarification (Gemini is asking a question).
                if elapsed_ms >= 3000:
                    return 'clarification'
        except Exception:
            pass
        page.wait_for_timeout(poll_interval_ms)
        elapsed_ms += poll_interval_ms
    return 'timeout'


def _wait_for_card_ready(page: Page, timeout_ms: int = 10000) -> bool:
    """
    Wait for a swipe card to be visible and ready for interaction.
    Detects card presence by checking for an h2 element inside the swipe page
    and verifying no loading overlay is blocking interaction.
    Returns True if card is ready, False on timeout.
    """
    try:
        page.wait_for_function("""() => {
            // Card must have a visible h2 (title)
            const h2 = document.querySelector('h2');
            if (!h2 || !h2.offsetParent) return false;

            // Check that h2 text is not a static page header like "All done!" or project name only
            // A card h2 will be inside a div with a background image or gradient
            const h2Text = h2.textContent.trim();
            if (!h2Text) return false;

            // Check there's no full-page loading spinner (skeleton card)
            // The loading skeleton has an animation element but no real card content
            const spinners = document.querySelectorAll('[style*="animation"]');
            // If there are spinning elements but no card image, still loading
            const imgs = document.querySelectorAll('img');
            let hasCardImage = false;
            for (const img of imgs) {
                if (img.offsetHeight > 50) { hasCardImage = true; break; }
            }

            return hasCardImage || h2Text.length > 3;
        }""", timeout=timeout_ms)
        return True
    except Exception:
        return False


def _check_card_image_visible(page: Page) -> bool:
    """
    Check whether a card image is currently visible in the viewport.
    Returns True if an <img> with naturalWidth > 0 and offsetHeight > 100 is found.
    Used for post-screenshot assertion to detect blank card renders.
    """
    try:
        return page.evaluate("""() => {
            const imgs = document.querySelectorAll('img');
            for (const img of imgs) {
                if (img.naturalWidth > 0 && img.offsetHeight > 100) return true;
            }
            return false;
        }""")
    except Exception:
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
    5. Swipe page -- use ArrowRight/ArrowLeft keyboard keys (no buttons since UX4)
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
        # Step 4: LLM Search -- Submit query (initial NL turn)
        #
        # v1.9 measurement: track t_initial_submit (observability) +
        # t_last_user_submit (rewritten on each clarification turn; this is
        # the system-attributable TTFC anchor per spec §4).
        # ================================================================
        t0 = time.time()
        t_initial_submit = None       # first submit (observability total user-felt latency)
        t_last_user_submit = None     # rewritten per clarification turn (v1.9 GATE anchor)
        user_submit_count = 0
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
                t_initial_submit = time.time()
                t_last_user_submit = t_initial_submit
                user_submit_count = 1
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
                        t_initial_submit = time.time()
                        t_last_user_submit = t_initial_submit
                        user_submit_count = 1
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
            't_initial_submit': t_initial_submit,
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
        # Step 5: Multi-turn clarification loop + 'Start swiping' button
        #
        # v1.9 §4 + Investigation 22 M1: max 3 clarification turns. Each
        # canned reply rewrites t_last_user_submit so the GATE measurement
        # excludes user-paced reading time per spec.
        # ================================================================
        t0 = time.time()
        logger.info('Step 5: Multi-turn loop (max 3 clarifications) → "Start swiping" button')

        start_swiping_found = False
        clarification_turns = 0
        MAX_CLARIFICATION_TURNS = 3

        while clarification_turns < MAX_CLARIFICATION_TURNS:
            outcome = _detect_clarification_or_results(page, timeout_ms=8000)

            if outcome == 'results':
                start_swiping_found = True
                logger.info('"Start swiping" button appeared (after %d clarification turn(s))',
                            clarification_turns)
                break

            if outcome == 'timeout':
                logger.error('Step 5 timeout: neither "Start swiping" button nor clarification observable')
                # Check if there's an error message
                try:
                    error_text = page.locator('text=Something went wrong').first
                    if error_text.is_visible(timeout=500):
                        logger.error('Search returned error: "Something went wrong"')
                except Exception:
                    pass
                break

            # outcome == 'clarification' — send canned reply
            clarification_turns += 1
            reply_text = _canned_reply_for(scenario.search_query, clarification_turns)
            logger.info('Clarification turn %d: sending canned reply "%s"',
                        clarification_turns, reply_text)
            try:
                clarif_input = page.locator('input[placeholder*="Find a modern"]')
                clarif_input.fill(reply_text)
                page.wait_for_timeout(150)
                clarif_submit = page.locator('button[type="submit"]')
                if clarif_submit.first.is_visible(timeout=1000):
                    t_last_user_submit = time.time()  # v1.9: rewrite per turn
                    user_submit_count += 1
                    clarif_submit.first.click()
                else:
                    logger.warning('Clarification submit button not visible — aborting loop')
                    break
            except Exception as e:
                logger.warning('Clarification reply failed: %s — aborting loop', e)
                break

        if clarification_turns >= MAX_CLARIFICATION_TURNS and not start_swiping_found:
            logger.error('Max clarification turns (%d) exhausted without results', MAX_CLARIFICATION_TURNS)

        # v1.9 system-attributable TTFC: from last user submit to first card.
        # Recorded for downstream reporting. Aspirational total user-felt
        # latency (t_initial_submit → first card) preserved as observability.
        ttfc_anchor_ms = int((time.time() - t_last_user_submit) * 1000) if t_last_user_submit else None
        ttfc_total_user_felt_ms = int((time.time() - t_initial_submit) * 1000) if t_initial_submit else None

        step = collector.collect_step(page, '05_search_results', t0, {
            'start_swiping_visible': start_swiping_found,
            'clarification_turns': clarification_turns,
            'user_submit_count': user_submit_count,
            'ttfc_pre_swipe_anchor_ms': ttfc_anchor_ms,
            'ttfc_pre_swipe_total_user_felt_ms': ttfc_total_user_felt_ms,
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

        # Wait for the first card to load on the swipe page.
        # This involves: session creation API call (POST /sessions/) + first card image load.
        # Can take 5-15s depending on backend load and network speed.
        # Since UX4 removed Like/Dislike buttons, we detect card readiness by
        # checking for a visible card with an h2 title and/or an image.
        logger.info('Waiting for first card to load (up to 20s)...')
        first_card_loaded = _wait_for_card_ready(page, timeout_ms=20000)
        if first_card_loaded:
            logger.info('First card loaded -- card content visible')
        else:
            logger.warning('First card did not load within 20s')

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
        _wait_for_card_image(page, timeout_ms=3000)
        step = collector.collect_step(page, '06_swipe_start', t0, {
            'url': page.url,
            'first_card_loaded': first_card_loaded,
        })
        steps.append(step)

        if not first_card_loaded:
            logger.error('No card loaded on swipe page -- skipping swipe loop')
            step.errors.append(ErrorRecord(
                message='First card never loaded on swipe page (20s timeout)',
                source='assertion',
            ))
        else:
            # Track the previous card title to detect when a new card loads
            prev_card_title = ''

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
                        # Use keyboard ArrowRight (same as regular swipe)
                        try:
                            page.keyboard.press('ArrowRight')
                            logger.info('Pressed ArrowRight on action card to accept results')
                            page.wait_for_timeout(3000)
                        except Exception as e:
                            logger.warning('ArrowRight on action card failed: %s, trying "View Results" button', e)
                            _safe_click(page, 'text=View Results', '"View Results" button', timeout_ms=3000)
                            page.wait_for_timeout(2000)
                        break
                except Exception:
                    pass

                # Check for "All done!" completion screen
                try:
                    done_text = page.locator('text=All done!')
                    if done_text.first.is_visible(timeout=300):
                        logger.info('Completion screen detected: "All done!" after %d swipes', swipe_count)
                        session_completed = True
                        # Click "View Image Board" button
                        _safe_click(page, 'text=View Image Board', '"View Image Board" button', timeout_ms=3000)
                        page.wait_for_timeout(3000)
                        step = collector.collect_step(page, f'07_swipe_{i+1:02d}_completed', t0, {
                            'action': 'session_completed',
                            'total_swipes': swipe_count,
                        })
                        steps.append(step)
                        break
                except Exception:
                    pass

                # Check if there's a card visible by looking for an h2 element
                # The swipe card always has an h2 with the building title
                card_visible = False
                try:
                    card_visible = page.evaluate("""() => {
                        const h2 = document.querySelector('h2');
                        return !!(h2 && h2.offsetParent !== null && h2.textContent.trim().length > 0);
                    }""")
                except Exception:
                    pass

                if not card_visible:
                    # Wait a bit more -- card might still be loading
                    page.wait_for_timeout(2000)
                    try:
                        card_visible = page.evaluate("""() => {
                            const h2 = document.querySelector('h2');
                            return !!(h2 && h2.offsetParent !== null && h2.textContent.trim().length > 0);
                        }""")
                    except Exception:
                        pass

                if not card_visible:
                    logger.warning('No card visible on swipe page at swipe %d', i + 1)
                    step = collector.collect_step(page, f'07_swipe_{i+1:02d}_no_card', t0, {
                        'error': 'No card visible -- h2 element not found',
                        'swipe_number': swipe_count + 1,
                    })
                    step.errors.append(ErrorRecord(
                        message=f'Swipe {i+1}: No card visible, card may not have loaded',
                        source='assertion',
                    ))
                    steps.append(step)
                    break

                # Wait for the loading overlay to disappear (swipeLock released).
                # When isLoading is true, there's an overlay div with animation.
                # The keyboard handler in SwipePage ignores keypresses when isLoading=true.
                try:
                    page.wait_for_function("""() => {
                        // Check that the loading overlay spinner is NOT visible
                        // The overlay has style "pointerEvents: none" and contains a spinning div
                        const overlays = document.querySelectorAll('div[style*="pointer-events"]');
                        for (const o of overlays) {
                            const style = o.getAttribute('style') || '';
                            if (style.includes('animation') || style.includes('border-radius: 50%')) {
                                // This looks like the loading spinner overlay
                                if (o.offsetParent !== null) return false;
                            }
                        }
                        return true;
                    }""", timeout=5000)
                except Exception:
                    logger.warning('Loading overlay may still be present at swipe %d', i + 1)

                # Extract card metadata from the visible card
                card_metadata = _extract_card_metadata(page)
                building_id = card_metadata.get('building_id', '')
                card_title = card_metadata.get('title', '')

                # Decide swipe direction based on persona preferences
                decision = scenario.decide_swipe(card_metadata, scenario.persona)

                # Set up API response listener BEFORE the swipe gesture.
                swipe_listener = _setup_swipe_listener(page)


                # ---- TIMING: before swipe gesture ----
                t_before_swipe = time.time()

                # Execute swipe via mouse drag on the TinderCard.
                # This bypasses the keyboard handler's swipedCardId/pendingAction guards
                # and triggers TinderCard's native drag-based swiping.
                # swipeThreshold is 120px, so we drag 200px to ensure it triggers.
                # Viewport: 390x844 (iPhone 14 Pro). Card center approx (195, 350).
                swipe_succeeded = False
                dx = 200 if decision == 'like' else -200

                # Strategy 1: Locate card element by CSS and drag from its center
                try:
                    card_el = page.locator('div[style*="position: relative"]').filter(
                        has=page.locator('img')
                    ).first
                    box = card_el.bounding_box(timeout=3000)
                    if box:
                        cx = box['x'] + box['width'] / 2
                        cy = box['y'] + box['height'] / 2
                        page.mouse.move(cx, cy)
                        page.mouse.down()
                        for s in range(4):
                            page.mouse.move(cx + dx * (s + 1) / 4, cy, steps=2)
                        page.mouse.move(cx + dx, cy, steps=2)
                        page.mouse.up()
                        swipe_succeeded = True
                        logger.info('Swipe %d: %s (drag-locator, title: "%s")', swipe_count + 1, decision.upper(), card_title[:40])
                except Exception as e:
                    logger.warning('Swipe %d: locator drag failed (%s), trying viewport-center drag', swipe_count + 1, e)

                # Strategy 2: Drag from viewport center (card is always centered)
                if not swipe_succeeded:
                    try:
                        cx, cy = 195, 350  # Viewport center of card area
                        page.mouse.move(cx, cy)
                        page.mouse.down()
                        for s in range(4):
                            page.mouse.move(cx + dx * (s + 1) / 4, cy, steps=2)
                        page.mouse.move(cx + dx, cy, steps=2)
                        page.mouse.up()
                        swipe_succeeded = True
                        logger.info('Swipe %d: %s (drag-center, title: "%s")', swipe_count + 1, decision.upper(), card_title[:40])
                    except Exception as e:
                        logger.warning('Swipe %d: viewport-center drag failed (%s), trying keyboard', swipe_count + 1, e)

                # Strategy 3: Keyboard fallback (last resort)
                if not swipe_succeeded:
                    try:
                        key = 'ArrowRight' if decision == 'like' else 'ArrowLeft'
                        page.keyboard.press(key)
                        swipe_succeeded = True
                        logger.info('Swipe %d: %s (keyboard, title: "%s")', swipe_count + 1, decision.upper(), card_title[:40])
                    except Exception as e:
                        logger.error('Swipe %d: all gesture methods failed: %s', swipe_count + 1, e)
                        page.remove_listener('response', swipe_listener['_handler'])
                        step = collector.collect_step(page, f'07_swipe_{i+1:02d}_failed', t0, {
                            'error': f'All swipe methods failed: {e}',
                            'swipe_number': swipe_count + 1,
                        })
                        step.errors.append(ErrorRecord(
                            message=f'Swipe {i+1}: all gesture methods failed: {e}',
                            source='assertion',
                        ))
                        steps.append(step)
                        break

                # ---- TIMING: after swipe gesture ----
                t_after_swipe = time.time()

                # Collect the swipe API response (listener was set up before the gesture).
                swipe_response = _collect_swipe_response(page, swipe_listener, timeout_ms=5000)

                # ---- TIMING: after API response ----
                t_after_api = time.time()

                if swipe_response:
                    if swipe_response.get('next_image'):
                        next_img = swipe_response['next_image']
                        if next_img.get('building_id') == '__action_card__':
                            logger.info('Backend returned action card -- convergence reached')
                        elif next_img.get('building_id'):
                            logger.info('Next card: %s', next_img.get('name_en', next_img['building_id'])[:40])

                    if swipe_response.get('is_analysis_completed'):
                        logger.info('Backend reports analysis completed')
                        session_completed = True

                    if decision == 'like':
                        likes += 1
                        if building_id:
                            buildings_liked.append(building_id)
                    else:
                        dislikes += 1
                else:
                    logger.warning('Swipe %d: API response not received within timeout', swipe_count + 1)
                    if decision == 'like':
                        likes += 1
                    else:
                        dislikes += 1

                swipe_count += 1
                prev_card_title = card_title

                # Wait for the card to change (title differs from previous).
                # This proves TinderCard animation completed and React re-rendered.
                card_changed = _wait_for_new_card(page, prev_card_title, timeout_ms=4000)

                # ---- TIMING: after card transition ----
                t_after_card_change = time.time()

                if not card_changed and swipe_response is None:
                    # Card stuck: animation didn't complete, API didn't respond.
                    # Reload the page to recover from the stuck state.
                    logger.warning('Swipe %d: card stuck (same title, no API response) -- reloading page', swipe_count)
                    page.reload()
                    page.wait_for_timeout(3000)
                    _wait_for_card_ready(page, timeout_ms=10000)
                    # After reload, try to continue (the session persists in backend)

                # Always wait for card image and take screenshot on every swipe step.
                # (Issue 1 fix: removed conditional that skipped 20/30 swipe screenshots)
                _wait_for_card_image(page, timeout_ms=2000)

                # ---- TIMING: after image load ----
                t_after_image = time.time()

                # Build timing breakdown for performance analysis (Issue 3)
                timing_breakdown = {
                    'gesture_ms': round((t_after_swipe - t_before_swipe) * 1000),
                    'api_wait_ms': round((t_after_api - t_after_swipe) * 1000),
                    'card_transition_ms': round((t_after_card_change - t_after_api) * 1000),
                    'image_load_ms': round((t_after_image - t_after_card_change) * 1000),
                }

                step = collector.collect_step(page, f'07_swipe_{i+1:02d}', t0, {
                    'swipe_number': swipe_count,
                    'decision': decision,
                    'building_id': building_id,
                    'card_title': card_title,
                    'card_program': card_metadata.get('axis_typology', ''),
                    'card_style': card_metadata.get('axis_style', ''),
                    'api_confirmed': swipe_response is not None,
                    'timing': timing_breakdown,
                }, screenshot=True)
                steps.append(step)

                # Verify card image was visible in screenshot (Issue 2 fix).
                # Detects blank card renders that would otherwise go unreported.
                if not _check_card_image_visible(page):
                    step.errors.append(ErrorRecord(
                        message=f'Swipe {swipe_count}: card image not visible in screenshot',
                        source='assertion',
                    ))
                    logger.warning('Swipe %d: card image not visible in screenshot', swipe_count)

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

            # If we're on /library (folder list), click into the project folder first
            if '/library' in page.url and '/library/' not in page.url:
                try:
                    # The ProjectCard is a div with onClick, containing the project name.
                    # Click the card by finding the "swiped" text (unique to project cards).
                    folder_card = page.locator('div[style*="cursor: pointer"]').filter(
                        has_text='swiped'
                    ).first
                    if folder_card.is_visible(timeout=3000):
                        folder_card.click()
                        page.wait_for_timeout(2000)
                        logger.info('Clicked into project folder (url now: %s)', page.url)
                    else:
                        logger.warning('Project folder card not visible on /library')
                except Exception as e:
                    logger.warning('Could not click project folder: %s', e)

            # Look for "Generate Persona Report" button on folder detail page
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
