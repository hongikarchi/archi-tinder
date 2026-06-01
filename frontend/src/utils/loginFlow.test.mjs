/**
 * utils/loginFlow.test.mjs
 * Unit tests for loginFlow.js using Node's built-in test runner (no extra deps).
 * Run with: node --test frontend/src/utils/loginFlow.test.mjs
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

// Import the module under test. Node ESM resolves relative paths from cwd,
// so run from the repo root or frontend/ directory.
import {
  LOGIN_SWIPE_ACTIONS,
  ONBOARDING_ROLES,
  normalizeGuestName,
  buildGuestLoginPayload,
  hasGoogleLogin,
  getLoginSwipeAction,
  isDisplayNameReady,
  isRoleReady,
  isGuestProfileReady,
} from './loginFlow.js'

// ---------------------------------------------------------------------------
// ONBOARDING_ROLES shape
// ---------------------------------------------------------------------------
describe('ONBOARDING_ROLES', () => {
  test('has exactly 3 entries', () => {
    assert.equal(ONBOARDING_ROLES.length, 3)
  })

  test('each entry has {value, label} string properties', () => {
    for (const role of ONBOARDING_ROLES) {
      assert.equal(typeof role.value, 'string', `${role.value}.value must be string`)
      assert.equal(typeof role.label, 'string', `${role.value}.label must be string`)
      assert.ok(role.value.length > 0, 'value must be non-empty')
      assert.ok(role.label.length > 0, 'label must be non-empty')
    }
  })

  test('contains the required 3 values', () => {
    const values = ONBOARDING_ROLES.map(r => r.value)
    const required = ['student', 'architect', 'other']
    for (const v of required) {
      assert.ok(values.includes(v), `missing role value: ${v}`)
    }
  })
})

// ---------------------------------------------------------------------------
// Login swipe action helpers
// ---------------------------------------------------------------------------
describe('LOGIN_SWIPE_ACTIONS', () => {
  test('maps left to returning and right to new', () => {
    assert.deepEqual(LOGIN_SWIPE_ACTIONS, { left: 'returning', right: 'new' })
  })
})

describe('getLoginSwipeAction', () => {
  test('returns returning for left swipes', () => {
    assert.equal(getLoginSwipeAction('left'), 'returning')
  })

  test('returns new for right swipes', () => {
    assert.equal(getLoginSwipeAction('right'), 'new')
  })

  test('returns null for unsupported directions', () => {
    assert.equal(getLoginSwipeAction('up'), null)
    assert.equal(getLoginSwipeAction('down'), null)
    assert.equal(getLoginSwipeAction(''), null)
    assert.equal(getLoginSwipeAction(null), null)
  })
})

// ---------------------------------------------------------------------------
// UI readiness helpers
// ---------------------------------------------------------------------------
describe('isDisplayNameReady', () => {
  test('accepts strings with non-whitespace after trim', () => {
    assert.equal(isDisplayNameReady('Alice'), true)
    assert.equal(isDisplayNameReady('  Alice  '), true)
  })

  test('rejects blank and non-string values', () => {
    assert.equal(isDisplayNameReady(''), false)
    assert.equal(isDisplayNameReady('   '), false)
    assert.equal(isDisplayNameReady(null), false)
    assert.equal(isDisplayNameReady(undefined), false)
    assert.equal(isDisplayNameReady(42), false)
  })
})

describe('isRoleReady', () => {
  test('accepts only values from ONBOARDING_ROLES', () => {
    for (const role of ONBOARDING_ROLES) {
      assert.equal(isRoleReady(role.value), true, `${role.value} should be ready`)
    }
  })

  test('rejects missing, blank, and unknown roles', () => {
    assert.equal(isRoleReady(''), false)
    assert.equal(isRoleReady('architects'), false)
    assert.equal(isRoleReady(' student '), false)
    assert.equal(isRoleReady(null), false)
  })
})

describe('isGuestProfileReady', () => {
  test('requires display name and role readiness', () => {
    assert.equal(isGuestProfileReady({ displayName: 'Alice', role: 'student' }), true)
  })

  test('rejects blank display name with valid role', () => {
    assert.equal(isGuestProfileReady({ displayName: '   ', role: 'student' }), false)
  })

  test('rejects valid display name with invalid role', () => {
    assert.equal(isGuestProfileReady({ displayName: 'Alice', role: 'unknown' }), false)
  })

  test('rejects missing profile object', () => {
    assert.equal(isGuestProfileReady(), false)
  })
})

// ---------------------------------------------------------------------------
// normalizeGuestName
// ---------------------------------------------------------------------------
describe('normalizeGuestName', () => {
  test('empty string returns Guest', () => {
    assert.equal(normalizeGuestName(''), 'Guest')
  })

  test('whitespace-only string returns Guest', () => {
    assert.equal(normalizeGuestName('   '), 'Guest')
  })

  test('non-string input returns Guest', () => {
    assert.equal(normalizeGuestName(null), 'Guest')
    assert.equal(normalizeGuestName(undefined), 'Guest')
    assert.equal(normalizeGuestName(42), 'Guest')
  })

  test('trims leading/trailing whitespace', () => {
    assert.equal(normalizeGuestName('  Alice  '), 'Alice')
  })

  test('caps at 30 characters', () => {
    const long = 'A'.repeat(40)
    const result = normalizeGuestName(long)
    assert.equal(result.length, 30)
    assert.equal(result, 'A'.repeat(30))
  })

  test('preserves names within the 30-char limit', () => {
    assert.equal(normalizeGuestName('Tester'), 'Tester')
  })
})

// ---------------------------------------------------------------------------
// buildGuestLoginPayload
// ---------------------------------------------------------------------------
describe('buildGuestLoginPayload', () => {
  test('consent_accepted is strictly true (not merely truthy)', () => {
    const payload = buildGuestLoginPayload({ displayName: 'Alice', role: 'architect' })
    assert.strictEqual(payload.consent_accepted, true)
  })

  test('consent_accepted is true even when displayName is empty', () => {
    const payload = buildGuestLoginPayload({ displayName: '', role: '' })
    assert.strictEqual(payload.consent_accepted, true)
  })

  test('display_name is normalized via normalizeGuestName', () => {
    const payload = buildGuestLoginPayload({ displayName: '  Bob  ', role: 'student' })
    assert.equal(payload.display_name, 'Bob')
  })

  test('empty displayName produces Guest', () => {
    const payload = buildGuestLoginPayload({ displayName: '', role: 'other' })
    assert.equal(payload.display_name, 'Guest')
  })

  test('onboarding_role is passed through', () => {
    const payload = buildGuestLoginPayload({ displayName: 'Alice', role: 'architect' })
    assert.equal(payload.onboarding_role, 'architect')
  })

  test('onboarding_role defaults to empty string when omitted', () => {
    const payload = buildGuestLoginPayload({ displayName: 'Alice' })
    assert.equal(payload.onboarding_role, '')
  })

  test('includes consent_policy_version', () => {
    const payload = buildGuestLoginPayload({ displayName: 'Alice', role: 'architect' })
    assert.equal(typeof payload.consent_policy_version, 'string')
    assert.ok(payload.consent_policy_version.length > 0)
  })
})

// ---------------------------------------------------------------------------
// hasGoogleLogin
// ---------------------------------------------------------------------------
describe('hasGoogleLogin', () => {
  test('empty string returns false', () => {
    assert.equal(hasGoogleLogin(''), false)
  })

  test('undefined returns false', () => {
    assert.equal(hasGoogleLogin(undefined), false)
  })

  test('null returns false', () => {
    assert.equal(hasGoogleLogin(null), false)
  })

  test('whitespace-only string returns false', () => {
    assert.equal(hasGoogleLogin('   '), false)
  })

  test('a real-looking client ID returns true', () => {
    assert.equal(hasGoogleLogin('123456789.apps.googleusercontent.com'), true)
  })

  test('any non-empty non-whitespace string returns true', () => {
    assert.equal(hasGoogleLogin('some-client-id'), true)
  })

  // Conditional-mount contract: GoogleLoginButton / GoogleVerifyButton are ONLY
  // rendered when hasGoogleLogin returns true, ensuring useGoogleLogin (which
  // requires GoogleOAuthProvider) is never called without its provider context.
  test('false result means Google hook components must not be mounted', () => {
    assert.equal(hasGoogleLogin(''), false)
    assert.equal(hasGoogleLogin(undefined), false)
    assert.equal(hasGoogleLogin('   '), false)
  })

  test('true result confirms GoogleOAuthProvider is present, safe to mount hook', () => {
    assert.equal(hasGoogleLogin('123456789.apps.googleusercontent.com'), true)
  })
})
