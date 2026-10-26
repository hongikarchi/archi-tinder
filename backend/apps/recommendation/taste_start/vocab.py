"""
vocab.py -- Option dictionaries for taste-start tag recognition.

Every axis is a dict  value -> VocabEntry(value, ko, en, hint):
  * value : the canonical DB / internal value (also the JEV option key)
  * ko/en : display labels
  * hint  : Korean + English description sent to JEV as the option's criterion
            and mined by the dictionary fallback for keywords.

Option values mirror the live building DB (queried 2026-10-10). The merged
`use` tag is built from two questions: PROGRAM (broad) and TYPOLOGY (specific).
"""
import re
from collections import namedtuple

VocabEntry = namedtuple('VocabEntry', 'value ko en hint')

_PAREN = re.compile(r'\([^)]*\)')


def _first_ko(hint):
    """First Korean term of a hint (before any '/' or em-dash), parentheticals stripped."""
    head = re.split(r'[/—]', _PAREN.sub('', hint))[0]
    return head.split(',')[0].strip()


def _build(raw, en=None, ko=None):
    out = {}
    for value, hint in raw.items():
        out[value] = VocabEntry(
            value,
            (ko or {}).get(value) or _first_ko(hint),
            (en or {}).get(value, value),
            hint,
        )
    return out


# -- use: PROGRAM (13, no 'Other') + TYPOLOGY (35) ----------------------------
PROGRAM = _build({
    'Housing': '주거, 주택, 집, 아파트, 하우스 / housing, house, home, residence',
    'Public': '공공시설, 시청, 청사, 도서관, 커뮤니티 센터 / civic, public building, library',
    'Office': '오피스, 사무실, 업무시설 / office, workplace',
    'Hospitality': '호텔, 숙소, 리조트, 레스토랑, 카페 / hotel, resort, restaurant',
    'Education': '학교, 대학, 유치원, 교육시설 / school, university, kindergarten',
    'Museum': '미술관, 박물관, 갤러리, 전시관 / museum, gallery',
    'Mixed Use': '복합시설, 주상복합 / mixed-use',
    'Landscape': '조경, 공원 / landscape, park',
    'Sports': '체육관, 수영장, 경기장, 스파 / sports, gym, pool, stadium',
    'Religion': '교회, 성당, 예배당, 사찰, 종교 건축 / church, chapel, temple, religious',
    'Healthcare': '병원, 의료시설, 요양원 / hospital, clinic, care home',
    'Infrastructure': '다리, 발전소, 기반시설 / bridge, infrastructure',
    'Transport': '역, 공항, 터미널 / station, airport, terminal',
})

TYPOLOGY = _build({
    'House': '단독주택, 독립 주택 한 채 (NOT generic 주택/주거) / detached house, single-family house',
    'Apartment': '아파트, 아파트 건물 (NOT generic 공동주거) / apartment building',
    'Housing': '주거 단지, 집합주거 단지를 명시한 경우만 (NOT plain 주거/주택) / housing complex, housing estate',
    'Student Housing': '기숙사 / student housing',
    'Care Home': '요양원, 실버타운 / care home',
    'Office': '오피스, 사무실 / office',
    'Museum': '미술관, 박물관 / museum',
    'Gallery': '갤러리, 화랑 / gallery',
    'Library': '도서관 / library',
    'School': '학교, 초중고 / school',
    'Kindergarten': '유치원, 어린이집 / kindergarten',
    'University': '대학, 캠퍼스 / university',
    'Hospital': '병원 / hospital',
    'Hotel': '호텔 / hotel',
    'Restaurant': '레스토랑, 식당, 카페 / restaurant, cafe',
    'Retail': '상점, 매장, 리테일 / shop, retail',
    'Shopping Centre': '쇼핑몰, 백화점 / shopping centre',
    'Bank': '은행 / bank',
    'Civic Building': '시청, 청사, 주민센터 / civic building',
    'Religious Building': '교회, 성당, 사찰 / church, temple',
    'Memorial': '기념관, 추모 공간 / memorial',
    'Theatre': '극장, 공연장 / theatre',
    'Concert Hall': '콘서트홀 / concert hall',
    'Pavilion': '파빌리온 / pavilion',
    'Park': '공원 / park',
    'Sports Centre': '체육관, 수영장, 스포츠센터 / sports centre',
    'Stadium': '경기장, 스타디움 / stadium',
    'Train Station': '기차역, 지하철역 / train station',
    'Airport': '공항 / airport',
    'Bridge': '다리, 교량 / bridge',
    'Car Park': '주차장, 주차 빌딩 / car park',
    'Industrial': '공장, 산업 시설 / factory',
    'Warehouse': '창고 / warehouse',
    'Winery': '와이너리, 양조장 / winery',
    'Mixed Use': '복합 건물, 주상복합 / mixed use',
})

STYLE = _build({
    'Contemporary': '현대 건축, 동시대 / contemporary',
    'Minimalist': '미니멀, 절제된 / minimalist',
    'Vernacular': '토속적, 전통 재료·지역 건축 / vernacular, traditional local',
    'Industrial': '공장 같은, 인더스트리얼 / industrial',
    'Organic': '유기적, 곡선, 자연 형태 / organic, curvy',
    'Modernist': '모더니즘, 모던 / modernist, modern',
    'High-Tech': '하이테크 / high-tech',
    'Brutalist': '브루탈리즘, 노출 콘크리트 덩어리 / brutalist',
    'Postmodern': '포스트모던 / postmodern',
    'Neo-Classical': '신고전주의, 고전적 / neoclassical',
    'Parametric': '파라메트릭, 비정형 곡면 / parametric',
    'Deconstructivist': '해체주의 / deconstructivist',
})

ATMOSPHERE = _build({
    'Serene': '고요한, 차분한, 평온한 / serene, calm',
    'Urban': '도시적인 / urban',
    'Contemplative': '사색적인, 명상적인, 빛이 드는 정적 / contemplative, meditative',
    'Intimate': '아늑한, 친밀한, 작은 스케일 / intimate, cozy',
    'Dynamic': '역동적인 / dynamic',
    'Warm': '따뜻한 분위기 / warm, welcoming',
    'Playful': '재미있는, 경쾌한 / playful',
    'Rustic': '소박한, 시골풍 / rustic',
    'Industrial': '거친 공장 분위기 / industrial mood',
    'Monumental': '웅장한, 압도적인 / monumental, grand',
    'Raw': '날것의, 거친 / raw',
    'Futuristic': '미래적인 / futuristic',
})

COLOR = _build({
    'Neutral': '무채색에 가까운 중립 색 / neutral',
    'Earth': '흙빛, 갈색 계열 / earth tones',
    'Light': '밝은, 흰 / light, white',
    'Warm': '따뜻한 색감(노랑·주황·나무색) / warm colors',
    'Vibrant': '선명한, 원색 / vibrant',
    'Dark': '어두운 / dark',
    'Cool': '차가운 색감, 푸른 / cool colors',
    'Monochrome': '흑백, 단색 / monochrome',
})

# -- country: canonical English name -> Korean names (first = display label) --
# Raw DB spellings of the same country live in normalization.COUNTRY_ALIASES.
# Jersey / Guernsey (1 building each) are intentionally omitted: their Korean
# names collide with ordinary words in the dictionary fallback.
_COUNTRY_KO = {
    'Italy': '이탈리아', 'Spain': '스페인', 'France': '프랑스', 'United States': '미국',
    'China': '중국', 'Portugal': '포르투갈', 'Germany': '독일', 'United Kingdom': '영국',
    'Switzerland': '스위스', 'Belgium': '벨기에', 'Mexico': '멕시코', 'Japan': '일본',
    'Netherlands': '네덜란드', 'Brazil': '브라질', 'Canada': '캐나다', 'India': '인도',
    'Australia': '호주', 'Argentina': '아르헨티나', 'Austria': '오스트리아', 'Sweden': '스웨덴',
    'South Korea': '한국, 대한민국', 'Greece': '그리스', 'Denmark': '덴마크', 'Thailand': '태국',
    'Chile': '칠레', 'Poland': '폴란드', 'Norway': '노르웨이', 'Vietnam': '베트남',
    'Russia': '러시아', 'Czechia': '체코', 'Iran': '이란', 'Ukraine': '우크라이나',
    'Slovenia': '슬로베니아', 'United Arab Emirates': '아랍에미리트, 두바이', 'Hungary': '헝가리',
    'Turkey': '튀르키예, 터키', 'Ireland': '아일랜드', 'Indonesia': '인도네시아',
    'Finland': '핀란드', 'Taiwan': '대만', 'Ecuador': '에콰도르', 'Israel': '이스라엘',
    'Croatia': '크로아티아', 'Singapore': '싱가포르', 'Lithuania': '리투아니아',
    'New Zealand': '뉴질랜드', 'Costa Rica': '코스타리카', 'Colombia': '콜롬비아',
    'South Africa': '남아프리카공화국, 남아공', 'Slovakia': '슬로바키아', 'Georgia': '조지아',
    'Romania': '루마니아', 'Peru': '페루', 'Morocco': '모로코', 'Iceland': '아이슬란드',
    'Hong Kong': '홍콩', 'Uruguay': '우루과이', 'Lebanon': '레바논', 'Malaysia': '말레이시아',
    'Paraguay': '파라과이', 'Luxembourg': '룩셈부르크', 'Latvia': '라트비아',
    'Saudi Arabia': '사우디아라비아', 'Serbia': '세르비아', 'Bulgaria': '불가리아',
    'Philippines': '필리핀', 'Cyprus': '키프로스, 사이프러스', 'Qatar': '카타르',
    'Kuwait': '쿠웨이트', 'Albania': '알바니아', 'Estonia': '에스토니아', 'Moldova': '몰도바',
    'Bangladesh': '방글라데시', 'Senegal': '세네갈', 'Burkina Faso': '부르키나파소',
    'Kenya': '케냐', 'Cuba': '쿠바', 'Panama': '파나마', 'Belarus': '벨라루스', 'Ghana': '가나',
    'Rwanda': '르완다', 'Bolivia': '볼리비아', 'Malta': '몰타', 'Palestine': '팔레스타인',
    'Guatemala': '과테말라', 'Mali': '말리', 'Cambodia': '캄보디아', 'Armenia': '아르메니아',
    'Kazakhstan': '카자흐스탄', 'Dominican Republic': '도미니카공화국', 'Jordan': '요르단',
    'Venezuela': '베네수엘라', 'Bahrain': '바레인', 'Angola': '앙골라',
    'Madagascar': '마다가스카르', 'Cabo Verde': '카보베르데', 'Tanzania': '탄자니아',
    'Egypt': '이집트', 'El Salvador': '엘살바도르', 'Montenegro': '몬테네그로',
    'Uganda': '우간다', 'Sri Lanka': '스리랑카', 'Algeria': '알제리',
    'Liechtenstein': '리히텐슈타인', "Côte d'Ivoire": '코트디부아르',
    'North Macedonia': '북마케도니아', 'Bosnia and Herzegovina': '보스니아 헤르체고비나',
    'Andorra': '안도라', 'Tunisia': '튀니지', 'Azerbaijan': '아제르바이잔',
    'Puerto Rico': '푸에르토리코', 'Nepal': '네팔', 'Ethiopia': '에티오피아',
    'Greenland': '그린란드', 'Mongolia': '몽골', 'Haiti': '아이티', 'Nigeria': '나이지리아',
    'Bahamas': '바하마', 'Monaco': '모나코', 'Laos': '라오스', 'Mozambique': '모잠비크',
    'Burundi': '부룬디', 'Niger': '니제르', 'Cameroon': '카메룬', 'North Korea': '북한',
    'Sudan': '수단', 'Maldives': '몰디브', 'Zambia': '잠비아', 'Antarctica': '남극',
    'Pakistan': '파키스탄', 'Mauritania': '모리타니', 'Myanmar': '미얀마',
    'Nicaragua': '니카라과', 'Uzbekistan': '우즈베키스탄', 'San Marino': '산마리노',
    'Gibraltar': '지브롤터', 'Antigua and Barbuda': '앤티가 바부다', 'Somalia': '소말리아',
    'Afghanistan': '아프가니스탄', 'Chad': '차드', 'DR Congo': '콩고민주공화국',
    'Kosovo': '코소보', 'Macao': '마카오', 'Bhutan': '부탄', 'Iraq': '이라크',
    'Martinique': '마르티니크', 'Botswana': '보츠와나', 'New Caledonia': '뉴칼레도니아',
    'Tajikistan': '타지키스탄', 'Vatican City': '바티칸', 'Sierra Leone': '시에라리온',
    'Djibouti': '지부티', 'Réunion': '레위니옹',
}
COUNTRY = _build(_COUNTRY_KO)

# -- material groups / architectural elements --------------------------------
# 'other' is a valid group value (normalization.py) but is never asked about.
MATERIAL = _build({
    'wood': '나무, 목재, 목조 / wood, timber',
    'metal': '철, 금속, 강철, 알루미늄 / steel, metal',
    'concrete': '콘크리트, 노출 콘크리트 / concrete',
    'stone': '돌, 석재, 대리석 / stone, marble',
    'brick': '벽돌, 조적 / brick, masonry',
    'plaster': '회벽, 미장, 하얀 벽 / plaster, render',
    'tile': '타일, 도자기 타일 / tile, ceramic tile',
    'earth': '흙, 흙벽, 다짐흙 / earth, rammed earth',
    'glass': '유리, 유리 커튼월 / glass',
    'fabric': '천, 직물, 패브릭 / fabric, textile',
    'plastic': '플라스틱, 폴리카보네이트, 아크릴 / plastic, polycarbonate',
})

ELEMENT = _build({
    'Facade': '파사드, 건물 외관 / facade',
    'Stair': '계단 / stair, staircase',
    'Roof': '지붕 / roof',
    'Entrance': '입구, 출입구 / entrance',
    'Garden': '정원 / garden',
    'Courtyard': '중정, 안뜰 / courtyard',
    'Corridor': '복도 / corridor',
    'Fireplace': '벽난로 / fireplace',
    'Atrium': '아트리움 / atrium',
    'Balcony': '발코니 / balcony',
    'Terrace': '테라스 / terrace',
    'Canopy': '캐노피, 차양 / canopy',
    'Column': '기둥 / column',
})

ERA = _build({
    'recent': '최근, 요즘, 최신, 신축 (only explicit time words: built in the last few years)',
    '21st_century': '21세기, 2000년대 이후 (only if the period is explicitly named) / 21st century',
    'modern_20th': '근대, 20세기 (explicit time words only; NOT the style words 모던/모더니즘) / 20th century',
    'historic': '옛날, 오래된, 고건축, 역사적인 / historic, old (before 1900)',
}, en={'recent': 'Recent', '21st_century': '21st century',
       'modern_20th': '20th century', 'historic': 'Historic'})

BUILT = _build({
    'built_only': 'Only completed, actually built buildings (예: "지어진 걸로", "실제로 완공된 것만")',
    'unbuilt_ok': 'Unbuilt / planned projects are also fine (예: "아직 안 지어져도 돼", "계획안도 괜찮아")',
    'unbuilt_only': 'Only planned / unbuilt / competition projects (예: "계획 중인 프로젝트만", "미준공")',
}, en={'built_only': 'Built only', 'unbuilt_ok': 'Unbuilt OK', 'unbuilt_only': 'Unbuilt only'},
    ko={'built_only': '지어진 건물만', 'unbuilt_ok': '미준공도 포함', 'unbuilt_only': '미준공 프로젝트만'})

# tag axis -> vocab dict for axes that map 1:1 onto a single vocab ('use' spans two).
AXIS_VOCAB = {
    'style': STYLE, 'atmosphere': ATMOSPHERE, 'color': COLOR, 'country': COUNTRY,
    'material': MATERIAL, 'element': ELEMENT, 'era': ERA, 'built': BUILT,
}


def criteria(vocab):
    """{value: hint} for a JEV `criteria` block."""
    return {value: entry.hint for value, entry in vocab.items()}
