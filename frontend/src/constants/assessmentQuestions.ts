/**
 * assessmentQuestions.js
 * 20-item personality assessment question bank.
 * axis: 1=작업방식(개념↔실무), 2=역할성향(리더↔서포터),
 *       3=협업방식(협업↔독립), 4=접근태도(혁신↔전통), 5=결정속도(신중↔즉흥)
 * reversed: true → raw Likert value is inverted before storage
 */

export const QUESTIONS = [
  // axis 1 (개념↔실무): 문항 0-3
  { id: 0, axis: 1, reversed: false, text_ko: '새로운 프로젝트를 시작할 때, 개념과 아이디어를 먼저 탐색하는 편이다.', text_en: 'When starting a new project, I tend to explore concepts and ideas first.' },
  { id: 1, axis: 1, reversed: true,  text_ko: '건축에서 이론적 완성도보다 실제 시공 가능성을 더 중요하게 생각한다.', text_en: 'In architecture, I value real-world buildability over theoretical completeness.' },
  { id: 2, axis: 1, reversed: true,  text_ko: '도면보다 모형이나 스케치 같은 손으로 만지는 결과물이 더 즐겁다.', text_en: 'I enjoy hands-on outputs like models or sketches more than drawings.' },
  { id: 3, axis: 1, reversed: false, text_ko: '건축의 사회적·문화적 맥락을 탐구하는 과정이 흥미롭다.', text_en: 'I find it interesting to explore the social and cultural context of architecture.' },
  // axis 2 (리더↔서포터): 문항 4-7
  { id: 4, axis: 2, reversed: false, text_ko: '팀에서 방향을 제시하고 의사결정을 주도하는 역할이 자연스럽다.', text_en: 'Setting direction and driving decisions for a team comes naturally to me.' },
  { id: 5, axis: 2, reversed: true,  text_ko: '팀원의 아이디어를 발전시키고 지원하는 것이 더 보람 있다.', text_en: 'I find it more rewarding to develop and support my teammates\' ideas.' },
  { id: 6, axis: 2, reversed: false, text_ko: '프로젝트가 잘못된 방향으로 가면 먼저 나서서 수정하려 한다.', text_en: 'When a project heads in the wrong direction, I step in first to correct it.' },
  { id: 7, axis: 2, reversed: true,  text_ko: '주목받기보다 팀 전체가 잘 되는 것이 더 중요하다.', text_en: 'The team succeeding as a whole matters more to me than getting attention.' },
  // axis 3 (협업↔독립): 문항 8-11
  { id: 8, axis: 3, reversed: false, text_ko: '여러 사람과 아이디어를 나누며 작업할 때 더 좋은 결과가 나온다.', text_en: 'I get better results when working by exchanging ideas with several people.' },
  { id: 9, axis: 3, reversed: true,  text_ko: '혼자 깊이 집중할 수 있을 때 최선의 작업이 나온다.', text_en: 'My best work comes when I can focus deeply on my own.' },
  { id: 10, axis: 3, reversed: false, text_ko: '다양한 관점이 충돌하는 논의 과정이 즐겁다.', text_en: 'I enjoy discussions where diverse perspectives clash.' },
  { id: 11, axis: 3, reversed: true,  text_ko: '협업보다 명확한 역할 분담과 개인 작업이 더 효율적이다.', text_en: 'Clear role division and individual work are more efficient than collaboration.' },
  // axis 4 (혁신↔전통): 문항 12-15
  { id: 12, axis: 4, reversed: false, text_ko: '기존에 없던 형태나 방식을 실험하는 것이 좋다.', text_en: 'I like experimenting with forms or methods that didn\'t exist before.' },
  { id: 13, axis: 4, reversed: true,  text_ko: '검증된 재료와 공법을 바탕으로 한 설계가 더 신뢰할 수 있다.', text_en: 'Designs based on proven materials and construction methods are more trustworthy.' },
  { id: 14, axis: 4, reversed: false, text_ko: '건축에서 파격적인 시도가 결국 더 오래 기억된다.', text_en: 'Bold, unconventional attempts in architecture end up being remembered longer.' },
  { id: 15, axis: 4, reversed: true,  text_ko: '지역의 역사와 전통을 반영한 건축이 더 가치 있다.', text_en: 'Architecture that reflects a region\'s history and tradition is more valuable.' },
  // axis 5 (신중↔즉흥, 보너스): 문항 16-19
  { id: 16, axis: 5, reversed: false, text_ko: '결정 전에 충분한 정보를 수집하고 분석한다.', text_en: 'I gather and analyze enough information before making a decision.' },
  { id: 17, axis: 5, reversed: true,  text_ko: '영감이 떠오르면 바로 스케치하거나 시작한다.', text_en: 'When inspiration strikes, I start sketching or working right away.' },
  { id: 18, axis: 5, reversed: false, text_ko: '계획 없이 시작하면 불안하다.', text_en: 'Starting without a plan makes me feel anxious.' },
  { id: 19, axis: 5, reversed: true,  text_ko: '즉흥적으로 결정한 것이 오히려 더 잘 맞을 때가 많다.', text_en: 'Decisions made on the spur of the moment often turn out to fit better.' },
]

// Localized at the render site via i18n key `assessmentCard.likert.<key>`
// (frontend/src/i18n/locales.js). LIKERT_LABELS (Korean literals) is retired —
// AssessmentCard.jsx now maps LIKERT_KEYS through useTranslation()'s t().
export const LIKERT_KEYS = ['stronglyDisagree', 'disagree', 'neutral', 'agree', 'stronglyAgree']
export const LIKERT_VALUES = [-2, -1, 0, 1, 2]
