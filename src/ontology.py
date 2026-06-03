# Banking/finance regulatory ontology — v0.
# Both extraction stages (GLiNER + LLM) read from this file.
# Iterate by editing here; track changes with comments noting why types were added/dropped.

ENTITIES = {
    'Person':                'Individuals such as signatories, executives, license holders.',
    'BankingInstitution':    'Commercial banks, branches, financial subsidiaries.',
    'RegulatoryBody':        'Central banks, ministries, tax/customs/social-insurance authorities, financial supervisory bodies (e.g., البنك المركزي المصري, الهيئة القومية للتأمين الاجتماعي, مأمورية الضرائب).',
    'Law':                   'Named laws with number and year (e.g., "Law 194/2020").',
    'Article':               'Article, section, or clause reference within a law.',
    'License':               'Licenses, permits, authorizations granted by a regulator.',
    'Document':              'Circulars, decrees, policy notes, reference documents.',
    'FinancialInstrument':   'Accounts, deposits, contracts, financial products.',
    'RegulatoryRequirement': 'Capital ratios, reserve requirements, thresholds.',
    'MonetaryAmount':        'Amounts with currency.',
    'Date':                  'Absolute dates and date ranges.',
}

# General-knowledge ontology for English-language corpora (e.g., MuSiQue / Wikipedia).
ENTITIES_EN = {
    'Person':       'Individual people, real or fictional.',
    'Organization': 'Companies, institutions, bands, teams, agencies, governments.',
    'Location':     'Countries, cities, regions, geographic features, landmarks.',
    'Work':         'Films, books, songs, albums, paintings, plays, video games.',
    'Event':        'Battles, wars, conferences, ceremonies, scheduled events.',
    'Date':         'Specific dates, years, decades, or date ranges.',
    'Nationality':  'National, ethnic, or cultural affiliations.',
    'Occupation':   'Jobs, professions, roles, titles.',
    'Award':        'Prizes, honors, decorations, recognitions.',
    'Language':     'Spoken or written languages.',
}

ENTITIES_BY_LANG = {'ar': ENTITIES, 'en': ENTITIES_EN}

RELATIONSHIPS = {
    'ISSUED_BY':      (['License', 'Document'],         ['RegulatoryBody', 'Person']),
    'GOVERNS':        (['Law', 'Article'],              ['BankingInstitution']),
    'AMENDS':         (['Law'],                         ['Law']),
    'SUPERSEDES':     (['Law'],                         ['Law']),
    'PART_OF':        (['Article'],                     ['Law']),
    'REQUIRES':       (['Law', 'Article'],              ['RegulatoryRequirement']),
    'SIGNED_BY':      (['Document', 'License'],         ['Person']),
    'EFFECTIVE_FROM': (['Law', 'License'],              ['Date']),
    'APPLIES_TO':     (['Law', 'Article'],              ['BankingInstitution']),
}

# Natural-language descriptions used to embed each relationship type so the
# retriever can score query–relation semantic similarity. Bilingual on purpose:
# BGE-M3 handles cross-lingual matching, but Arabic queries hit Arabic phrasings
# more reliably.
RELATIONSHIP_DESCRIPTIONS = {
    'ISSUED_BY':      'صادر عن جهة، يصدر من، صادر بقرار من — issued by, granted by, authorized by',
    'GOVERNS':        'يحكم، ينظم، يضع قواعد على — governs, regulates, controls',
    'AMENDS':         'يعدل، يغير، يحدث قانوناً — amends, modifies, updates',
    'SUPERSEDES':     'يلغي، يحل محل، يستبدل — supersedes, replaces, overrides',
    'PART_OF':        'مادة من، فقرة من، جزء من قانون — part of, section of, contained in',
    'REQUIRES':       'يتطلب، يوجب، يفرض شرطاً — requires, mandates, demands',
    'SIGNED_BY':      'موقع من، اعتمد بتوقيع — signed by, approved by',
    'EFFECTIVE_FROM': 'نافذ من تاريخ، يسري من — effective from, in force since',
    'APPLIES_TO':     'ينطبق على، يسري على، يخضع له — applies to, covers, pertains to',
}
