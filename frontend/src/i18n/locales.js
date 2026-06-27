/**
 * Translation dictionaries — Korea-first, bilingual only.
 * Keys use dot-path notation: 'tabbar.discovery', 'settings.appearance', etc.
 * Expand nested dicts here; useTranslation() resolves paths at runtime.
 */
export const locales = {
  ko: {
    tabbar: {
      discovery: '디스커버리',
      taste:     '취향',
      profile:   '프로필',
    },
    settings: {
      appearance: '화면 설정',
      language:   '언어',
    },
    login: {
      tagline: '스와이프 한 번으로 시작, 내 취향 프로필로 완성.',
      prompt: {
        choice:    '어떻게 맞이할지 알려주세요.',
        returning: '저장된 프로필로 복원할 수 있어요.',
        register:  '아이디와 비밀번호로 계정을 만드세요.',
        profile:   '이름과 목표가 첫 덱을 만들어요.',
        consent:   '오른쪽으로 스와이프하면 게스트 프로필이 생성돼요.',
      },
      caption: {
        choice:    '왼쪽 스와이프 — 기존 계정 | 오른쪽 스와이프 — 게스트 시작',
        returning: 'Google 또는 아이디·비밀번호로 돌아오세요.',
        register:  '아이디는 3자 이상, 비밀번호는 8자 이상이어야 해요.',
        profile:   '프로필 정보가 첫 추천 덱을 구성해요.',
        consent:   '왼쪽 — 돌아가기 | 오른쪽 — 동의하고 입장',
      },
      intro: {
        eyebrow: '시작하기 전에',
        title:   '스와이프로 취향을 발견하세요',
        body:    '카드를 왼쪽·오른쪽으로 스와이프해\n건축 스타일에 반응하세요.\n10~15장이면 취향 프로필이 완성됩니다.',
        cta:     '시작하기',
      },
      choice: {
        eyebrow:      '첫 카드',
        title:        '처음 방문하셨나요?',
        left:         { label: '기존 계정', sub: '왼쪽 스와이프' },
        right:        { label: '새 프로필', sub: '오른쪽 스와이프' },
        registerLink: '아이디 · 비밀번호로 가입',
      },
      returning: {
        eyebrow:            '기존 계정',
        title:              '저장된 프로필로 계속하세요.',
        google:             'Google로 계속하기',
        googleUnavailable:  '이 환경에서는 Google 로그인을 사용할 수 없어요. VITE_GOOGLE_CLIENT_ID를 설정하면 기존 계정을 불러올 수 있어요.',
        divider:            '또는',
        handle: {
          placeholder: '아이디 (handle)',
          aria:        '아이디',
        },
        password: {
          placeholder: '비밀번호',
          aria:        '비밀번호',
        },
        submit: '아이디 · 비밀번호로 로그인',
      },
      register: {
        eyebrow: '새 계정',
        title:   '아이디로 가입합니다.',
        name: {
          label:       '이름 (선택)',
          placeholder: '홍길동',
        },
        handle: {
          label:       '아이디 *',
          placeholder: '예: dain_architect',
        },
        password: {
          label:       '비밀번호 * (8자 이상)',
          placeholder: '••••••••',
        },
        submit: '가입하기',
      },
      profile: {
        eyebrow: '새 게스트',
        title:   '누가 스와이프하는지 알려주세요.',
        displayName: {
          label:       '표시 이름',
          placeholder: 'Alex',
        },
        jobRole: {
          label:       '직업 (선택)',
          placeholder: '건축학과 학생',
        },
        affiliation: {
          label:       '소속 (선택)',
          placeholder: '고려대학교',
        },
        objective: {
          label:      '목표',
          selected:   '선택됨',
          required:   '필수',
          aria:       '목표 선택',
          student:    '학생',
          architect:  '건축가',
          other:      '그냥 둘러보기',
        },
        continueBtn: '계속',
      },
      consent: {
        eyebrow: '동의',
        title:   '게스트 계정을 만들겠습니다.',
        summary: {
          name:        '이름',
          objective:   '목표',
          role:        '직업',
          affiliation: '소속',
          notSelected: '선택 안 됨',
        },
        body:  '계속하면 archibe가 이 게스트 프로필로 서비스를 제공하고 취향 신호를 저장하는 데 동의하는 것입니다.',
        left:  { label: '돌아가기', sub: '왼쪽 스와이프' },
        right: { label: '동의하고 입장', sub: '오른쪽 스와이프' },
      },
      common: {
        back: '뒤로',
      },
      dev: {
        button: 'Dev login',
      },
      error: {
        googleFailed:          'Google 로그인 실패: {detail}',
        googleError:           'Google 로그인 오류: {detail}',
        popupBlocked:          '팝업이 브라우저에서 차단되었어요. 이 사이트의 팝업을 허용해주세요.',
        loginStart:            '로그인을 시작할 수 없어요. 브라우저 설정을 확인해주세요.',
        displayNameRequired:   '표시 이름을 입력해야 계속할 수 있어요.',
        objectiveRequired:     '목표를 선택해야 계속할 수 있어요.',
        profileIncomplete:     '동의 전에 표시 이름과 목표를 입력해주세요.',
        consentRequired:       '게스트 프로필을 만들기 전에 동의가 필요해요.',
        consentRetry:          '계속하려면 동의가 필요해요. 동의 단계를 다시 시도해주세요.',
        signInFailed:          '로그인 실패: {detail}',
        loginFailed:           '로그인에 실패했습니다.',
        registerFailed:        '가입에 실패했습니다.',
        devFailed:             'Dev 로그인 실패: {detail}',
      },
    },
  },
  en: {
    tabbar: {
      discovery: 'Discovery',
      taste:     'Taste',
      profile:   'Profile',
    },
    settings: {
      appearance: 'Appearance',
      language:   'Language',
    },
    login: {
      tagline: 'Start with a swipe, then tune a taste profile.',
      prompt: {
        choice:    'Tell me how to welcome you.',
        returning: 'I can restore your verified profile.',
        register:  'Create your account with a handle and password.',
        profile:   'A name and objective shape your first deck.',
        consent:   'One right swipe creates the guest profile.',
      },
      caption: {
        choice:    'Swipe left — existing account | Swipe right — start as guest',
        returning: 'Return with Google or your handle and password.',
        register:  'Handle at least 3 characters, password at least 8.',
        profile:   'Your profile shapes the first recommendation deck.',
        consent:   'Swipe left — go back | Swipe right — consent and enter',
      },
      intro: {
        eyebrow: 'Before you begin',
        title:   'Discover your taste through swipes',
        body:    'Swipe cards left or right to react\nto architectural styles.\n10–15 swipes builds your taste profile.',
        cta:     'Get started',
      },
      choice: {
        eyebrow:      'First card',
        title:        'Are you new here?',
        left:         { label: 'Returning', sub: 'Left swipe' },
        right:        { label: 'New profile', sub: 'Right swipe' },
        registerLink: 'Register with handle & password',
      },
      returning: {
        eyebrow:            'Returning',
        title:              'Continue with your saved profile.',
        google:             'Continue with Google',
        googleUnavailable:  'Google login is unavailable in this environment. Set VITE_GOOGLE_CLIENT_ID to enable returning accounts.',
        divider:            'or',
        handle: {
          placeholder: 'Handle',
          aria:        'Handle',
        },
        password: {
          placeholder: 'Password',
          aria:        'Password',
        },
        submit: 'Sign in with handle',
      },
      register: {
        eyebrow: 'New account',
        title:   'Register with a handle.',
        name: {
          label:       'Display name (optional)',
          placeholder: 'Alex',
        },
        handle: {
          label:       'Handle *',
          placeholder: 'e.g. dain_architect',
        },
        password: {
          label:       'Password * (8+ characters)',
          placeholder: '••••••••',
        },
        submit: 'Create account',
      },
      profile: {
        eyebrow: 'New guest',
        title:   'Tell me who is swiping.',
        displayName: {
          label:       'Display name',
          placeholder: 'Alex',
        },
        jobRole: {
          label:       'Job role (optional)',
          placeholder: 'Architecture Student',
        },
        affiliation: {
          label:       'Affiliation (optional)',
          placeholder: 'Korea University',
        },
        objective: {
          label:      'Objective',
          selected:   'Selected',
          required:   'Required',
          aria:       'Select your objective',
          student:    'Student',
          architect:  'Architect',
          other:      'Just exploring',
        },
        continueBtn: 'Continue',
      },
      consent: {
        eyebrow: 'Consent',
        title:   'Create the guest account.',
        summary: {
          name:        'Name',
          objective:   'Objective',
          role:        'Role',
          affiliation: 'Affiliation',
          notSelected: 'Not selected',
        },
        body:  'By continuing, you agree that archibe can use this guest profile to provide the service and save your taste signals.',
        left:  { label: 'Back', sub: 'Left swipe' },
        right: { label: 'Consent and enter', sub: 'Right swipe' },
      },
      common: {
        back: 'Back',
      },
      dev: {
        button: 'Dev login',
      },
      error: {
        googleFailed:          'Google login failed: {detail}',
        googleError:           'Google login error: {detail}',
        popupBlocked:          'Popup was blocked by the browser. Please allow popups for this site.',
        loginStart:            'Login could not start. Please check your browser settings.',
        displayNameRequired:   'Enter a display name to continue.',
        objectiveRequired:     'Choose an objective to continue.',
        profileIncomplete:     'Add a display name and objective before consent.',
        consentRequired:       'Consent is required before creating a guest profile.',
        consentRetry:          'Consent is required to continue. Please try the consent step again.',
        signInFailed:          'Sign in failed: {detail}',
        loginFailed:           'Login failed. Please try again.',
        registerFailed:        'Registration failed. Please try again.',
        devFailed:             'Dev login failed: {detail}',
      },
    },
  },
}
