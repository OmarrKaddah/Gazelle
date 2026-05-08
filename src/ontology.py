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
