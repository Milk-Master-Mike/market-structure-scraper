# Security policy

Report vulnerabilities privately through GitHub Security Advisories. Never put
credentials or private portfolio data in an issue.

Live mode requires an identified `MARKET_STRUCTURE_USER_AGENT`. It is read from
the environment and is never returned, exported, or logged. Scraped text is
untrusted data: parsers accept bounded text responses, normalize known fields,
and never execute source content. Cache files are operational and contain no
provider credentials or user research history.

