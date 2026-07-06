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
    discovery: {
      loading: '취향 탐색 중…',
    },
    settings: {
      appearance: '화면 설정',
      language:   '언어',
      theme:      '테마',
      font:       '글꼴',
      preview:    '미리보기',
    },
    notifications: {
      title: '알림',
      loading: '불러오는 중...',
      fetchError: '알림을 불러올 수 없습니다.',
      empty: '알림이 없습니다',
      loadMore: '더 보기',
      unreadAriaSuffix: '읽지 않음',
      bellAria: '알림',
      sentence: {
        reaction: '{name}님이 회원님의 프로젝트를 좋아합니다',
        passwordChanged: '비밀번호가 변경되었습니다',
        newLogin: '새 기기에서 로그인되었습니다',
      },
      settings: {
        disclaimer: '이메일·푸시 알림은 추후 지원됩니다',
        categories: {
          social: {
            label: '소셜 활동',
            hint: '팔로우 · 좋아요 · 댓글 · 멘션',
          },
          content: {
            label: '내 보드 · 프로젝트',
            hint: '저장 · 공유 · 추천 노출',
          },
          security: {
            label: '계정 보안',
            hint: '새 기기 로그인 · 비밀번호 변경',
            lockedHint: '보안 알림은 계정 보호를 위해 항상 켜집니다.',
          },
          recommend: {
            label: '추천 · 트렌드',
            hint: '개인화 추천 · 주간 다이제스트',
          },
          marketing: {
            label: '마케팅 · 이벤트',
            hint: '프로모션 안내',
          },
        },
        inAppToggle: '앱 내 알림',
        loading: '불러오는 중...',
        fetchError: '알림 설정을 불러올 수 없습니다.',
        saveError: '저장에 실패했습니다. 다시 시도해주세요.',
      },
    },
    profileEdit: {
      role: {
        label:      '직업 (Role)',
        blankOption: '선택 안 함',
        legacyHint: '기존 입력: {role}',
      },
    },
    login: {
      prompt: {
        choice:      '당신의 명함을 준비할게요.',
        returning:   '다시 만나서 반가워요.',
        credentials: '명함에 새길 이름이에요.',
        profile:     '첫 추천 덱이 여기서 정해져요.',
        consent:     '이 명함으로 시작할까요?',
      },
      intro: {
        eyebrow: '시작하기 전에',
        title:   '스와이프로 취향을 발견하세요',
        body:    '카드를 왼쪽·오른쪽으로 스와이프해\n건축 스타일에 반응하세요.\n10~15장이면 취향 프로필이 완성됩니다.',
        cta:     '시작하기',
      },
      choice: {
        eyebrow: '첫 카드',
        title:   '처음 방문하셨나요?',
        left:    { label: '기존 계정', sub: '왼쪽 스와이프' },
        right:   { label: '새 프로필', sub: '오른쪽 스와이프' },
      },
      returning: {
        eyebrow:            '기존 계정',
        title:              '저장된 프로필로 계속하세요.',
        google:             'Google로 인증 · 로그인',
        googleUnavailable:  '이 환경에서는 Google 로그인을 사용할 수 없어요. VITE_GOOGLE_CLIENT_ID를 설정하면 기존 계정을 불러올 수 있어요.',
        googleSignupRequired: 'Google 계정으로 가입된 ID가 없어요. 먼저 ID를 만들어주세요.',
        divider:            '또는',
        id: {
          placeholder: 'ID',
          aria:        'ID',
        },
        password: {
          placeholder: '비밀번호',
          aria:        '비밀번호',
        },
        submit: 'ID · 비밀번호로 로그인',
      },
      credentials: {
        eyebrow: '새 계정',
        title:   'ID와 비밀번호를 정해주세요.',
        id: {
          label:       'ID *',
          placeholder: '예: dain_kim · 2–20자',
          aria:        'ID',
          checking:    '확인 중…',
          available:   '사용 가능',
          taken:       '이미 사용 중',
        },
        checkBtn: '중복확인',
        password: {
          label:       '비밀번호 *',
          placeholder: '8자 이상',
          aria:        '비밀번호',
        },
        continueBtn: '계속',
      },
      profile: {
        eyebrow: '새 프로필',
        title:   '누가 스와이프하는지 알려주세요.',
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
          designer:   '디자이너',
          enthusiast: '건축 애호가',
          other:      '그냥 둘러보기',
        },
        continueBtn: '계속',
      },
      consent: {
        eyebrow:   '명함 미리보기',
        finePrint: '오른쪽으로 스와이프하면 archibe의 서비스 제공과 취향 신호 저장에 동의하는 것입니다 · 정책 v1.0',
        left:  { label: '돌아가기', sub: '왼쪽 스와이프' },
        right: { label: '발급', sub: '오른쪽 스와이프' },
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
        googleSignupRequired:  'Google 계정으로 가입된 ID가 없어요. 먼저 ID를 만들어주세요.',
        popupBlocked:          '팝업이 브라우저에서 차단되었어요. 이 사이트의 팝업을 허용해주세요.',
        loginStart:            '로그인을 시작할 수 없어요. 브라우저 설정을 확인해주세요.',
        idRequired:            'ID를 입력해야 계속할 수 있어요.',
        idInvalid:             'ID는 2-20자, 한글·영문·숫자·밑줄만 허용, 공백 불가예요.',
        idNotConfirmed:        '먼저 중복확인을 해주세요.',
        objectiveRequired:     '목표를 선택해야 계속할 수 있어요.',
        profileIncomplete:     '동의 전에 ID, 비밀번호, 목표를 입력해주세요.',
        consentRequired:       '계정을 만들기 전에 동의가 필요해요.',
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
    discovery: {
      loading: 'Exploring your taste…',
    },
    settings: {
      appearance: 'Appearance',
      language:   'Language',
      theme:      'Theme',
      font:       'Font',
      preview:    'Preview',
    },
    notifications: {
      title: 'Notifications',
      loading: 'Loading...',
      fetchError: 'Could not load notifications.',
      empty: 'No notifications yet',
      loadMore: 'Load more',
      unreadAriaSuffix: 'unread',
      bellAria: 'Notifications',
      sentence: {
        reaction: '{name} liked your project',
        passwordChanged: 'Your password was changed',
        newLogin: 'New sign-in from a new device',
      },
      settings: {
        disclaimer: 'Email and push notifications are coming later',
        categories: {
          social: {
            label: 'Social activity',
            hint: 'Follows · likes · comments · mentions',
          },
          content: {
            label: 'My boards · projects',
            hint: 'Saves · shares · recommendation exposure',
          },
          security: {
            label: 'Account security',
            hint: 'New device login · password changes',
            lockedHint: 'Security notifications are always on to protect your account.',
          },
          recommend: {
            label: 'Recommendations · trends',
            hint: 'Personalized recommendations · weekly digest',
          },
          marketing: {
            label: 'Marketing · events',
            hint: 'Promotional updates',
          },
        },
        inAppToggle: 'In-app notifications',
        loading: 'Loading...',
        fetchError: 'Could not load notification settings.',
        saveError: 'Save failed. Please try again.',
      },
    },
    profileEdit: {
      role: {
        label:      'Role',
        blankOption: 'Not set',
        legacyHint: 'Previously: {role}',
      },
    },
    login: {
      prompt: {
        choice:      'Let me prepare your card.',
        returning:   'Good to see you again.',
        credentials: 'The name printed on your card.',
        profile:     'This shapes your first deck.',
        consent:     'Shall we issue this card?',
      },
      intro: {
        eyebrow: 'Before you begin',
        title:   'Discover your taste through swipes',
        body:    'Swipe cards left or right to react\nto architectural styles.\n10–15 swipes builds your taste profile.',
        cta:     'Get started',
      },
      choice: {
        eyebrow: 'First card',
        title:   'Are you new here?',
        left:    { label: 'Returning', sub: 'Left swipe' },
        right:   { label: 'New profile', sub: 'Right swipe' },
      },
      returning: {
        eyebrow:              'Returning',
        title:                'Continue with your saved profile.',
        google:               'Verify / sign in with Google',
        googleUnavailable:    'Google login is unavailable in this environment. Set VITE_GOOGLE_CLIENT_ID to enable returning accounts.',
        googleSignupRequired: 'No account linked to this Google account. Please create an ID first.',
        divider:              'or',
        id: {
          placeholder: 'ID',
          aria:        'ID',
        },
        password: {
          placeholder: 'Password',
          aria:        'Password',
        },
        submit: 'Sign in with ID',
      },
      credentials: {
        eyebrow: 'New account',
        title:   'Choose your ID and password.',
        id: {
          label:       'ID *',
          placeholder: 'e.g. dain_kim · 2–20 chars',
          aria:        'ID',
          checking:    'Checking…',
          available:   'Available',
          taken:       'Already taken',
        },
        checkBtn: 'Check',
        password: {
          label:       'Password *',
          placeholder: '8+ characters',
          aria:        'Password',
        },
        continueBtn: 'Continue',
      },
      profile: {
        eyebrow: 'New profile',
        title:   'Tell me who is swiping.',
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
          designer:   'Designer',
          enthusiast: 'Architecture Enthusiast',
          other:      'Just exploring',
        },
        continueBtn: 'Continue',
      },
      consent: {
        eyebrow:   'Card preview',
        finePrint: 'Swiping right means you agree that archibe provides the service and stores your taste signals · policy v1.0',
        left:  { label: 'Back', sub: 'Left swipe' },
        right: { label: 'Issue', sub: 'Right swipe' },
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
        googleSignupRequired:  'No account found for this Google account. Create an ID first.',
        popupBlocked:          'Popup was blocked by the browser. Please allow popups for this site.',
        loginStart:            'Login could not start. Please check your browser settings.',
        idRequired:            'Enter an ID to continue.',
        idInvalid:             'ID must be 2–20 characters, Hangul or letters/digits/underscore, no spaces.',
        idNotConfirmed:        'Please confirm ID availability first.',
        objectiveRequired:     'Choose an objective to continue.',
        profileIncomplete:     'Complete ID, password, and objective before consent.',
        consentRequired:       'Consent is required before creating an account.',
        consentRetry:          'Consent is required to continue. Please try the consent step again.',
        signInFailed:          'Sign in failed: {detail}',
        loginFailed:           'Login failed. Please try again.',
        registerFailed:        'Registration failed. Please try again.',
        devFailed:             'Dev login failed: {detail}',
      },
    },
  },
}
