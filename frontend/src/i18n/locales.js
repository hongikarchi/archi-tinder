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
  },
}
