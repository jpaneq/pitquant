# ADR-0051 — Source-specific PPoG alias

Accepted 2026-10-05, explicit human instruction. `document-typo-alias-v2` maps only `PPoG Industries, Inc.` in N-30D accession `0001193125-17-355427` to `PPG Industries, Inc.`. Other strings and other filings are untouched. No fuzzy matcher is introduced.

The raw member and original document remain unchanged. The application verifies the archived source SHA and raw string, resolves the canonical PPG security using its official NPORT CUSIP 693506107, archives a versioned JSON audit and uses the existing SAME_SECURITY_IDENTITY_LINK to join duplicate identity representations. This is an identity equivalence, not a corporate succession, index exit or entry. No effective date is invented.

The audit contains source filing, document, date/hash, raw/resolved name and security, issuer when known, evidence type and version. An initial v1 audit incorrectly described the 2017Q3 13F bridge as sufficient; the v2 audit supersedes that description with the actual approved typo + identified NPORT evidence. The historical record is retained, not silently edited. A missing issuer linkage stays null rather than being inferred.
