# ruff: noqa: E501  (regexes quote official text verbatim)
"""WHERE to look for official identity evidence, and WHICH sentences must be present.

This file is NOT evidence: ``official_identity.record_*`` records a claim only when every
``checks`` pattern matches the archived original document. Every entry below was read in the
original document before it was written (see docs/OFFICIAL_IDENTITY_EVIDENCE.md, generated).
"""

from __future__ import annotations

from datetime import date

from pitquant.data.providers.official_identity import CodeEvidenceSpec, Doc, TransitionSpec

CNMV = "https://www.cnmv.es/webservices/verdocumento/ver?"
BME_IO = "https://www.bolsasymercados.es/bme-exchange/docs/regula/SBolsas/esp/instrucc/"

TRANSITIONS: tuple[TransitionSpec, ...] = (
    TransitionSpec(
        key="MTS-2017-reverse-split",
        issuer="ARCELORMITTAL, S.A.",
        old_isin="LU0323134006",
        new_isin="LU1598757687",
        kind="REVERSE_SPLIT",
        continuity="SAME_SECURITY",
        effective=date(2017, 5, 22),
        docs=(
            Doc(
                "issuer notice via CNMV (registro 251971, 12/05/2017)",
                CNMV + "e=Oyxe7f5sj%2fMkwpClNVWVIrojc5caDaczWitwUsYwRmRQSRh0dt1K2vXNhAR3mLSV",
                (
                    r"will become effective on 22 May 2017",
                    r"consolidate each three existing shares",
                    r"Spanish stock exchanges of Barcelona, Bilbao, Madrid and Valencia \(MTS\)",
                ),
            ),
            Doc(
                "issuer notice via CNMV (registro 252333, 22/05/2017)",
                CNMV + "e=zynpuaJLVU0rFQ40M7Els7ojc5caDaczWitwUsYwRmRQSRh0dt1K2vXNhAR3mLSV",
                (
                    r"has completed the consolidation of each three existing shares",
                    r"Reverse Stock Split",
                ),
            ),
        ),
    ),
    TransitionSpec(
        key="PHM-2020-contrasplit",
        issuer="PHARMA MAR, S.A.",
        old_isin="ES0169501030",
        new_isin="ES0169501022",
        kind="REVERSE_SPLIT",
        continuity="SAME_SECURITY",
        effective=date(2020, 7, 22),
        docs=(
            Doc(
                "CNMV OIR 3518, 22/07/2020",
                CNMV + "t=%7b77d9824f-668a-4fab-adf6-b8a8ff16a4ba%7d",
                (
                    r"una acci[oó]n nueva por cada 12 acciones preexistentes",
                    r"en el d[ií]a de hoy, las 18\.554\.107 acciones ordinarias nuevas",
                    r"admitidas a cotizaci[oó]n en las Bolsas de Madrid, Barcelona, Bilbao y Valencia",
                    r"C[oó]digo ISIN: ES0169501030",
                    r"C[oó]digo ISIN: ES0169501022",
                ),
            ),
            Doc(
                "CNMV OIR 3401, 14/07/2020",
                CNMV + "t=%7b3797a21f-9d46-45e7-9b8b-c1ed30a2fe6b%7d",
                (r"surtir[aá] efectos burs[aá]tiles el pr[oó]ximo d[ií]a 22 de julio de 2020",),
            ),
        ),
        nominals=("0,05", "0,60"),
    ),
    TransitionSpec(
        key="REE-2016-split",
        issuer="RED ELECTRICA CORPORACION, S.A.",
        old_isin="ES0173093115",
        new_isin="ES0173093024",
        kind="SPLIT",
        continuity="SAME_SECURITY",
        effective=date(2016, 7, 11),
        docs=(
            Doc(
                "CNMV hecho relevante 240218, 28/06/2016",
                CNMV + "e=VBD0lrCcuITtbW6CZo8M5qfqoTZheLsWaW8eg8EG1exQSRh0dt1K2vXNhAR3mLSV",
                (
                    r"next 11 of July 2016 the trading of the new shares",
                    r"four new shares for each old share",
                    r"from two euros .{0,6} to fifty cents",
                ),
            ),
        ),
        nominals=("2,00", "0,50"),
    ),
    TransitionSpec(
        key="GRF-2016-split",
        issuer="GRIFOLS, S.A.",
        old_isin="ES0171996012",
        new_isin="ES0171996087",
        kind="SPLIT",
        continuity="SAME_SECURITY",
        effective=date(2016, 1, 4),
        docs=(
            Doc(
                "CNMV hecho relevante 233601, 30/12/2015 (scanned: OCR)",
                CNMV + "e=Cks%2fkcHyRhulBjaj9Xn%2flafqoTZheLsWaW8eg8EG1exQSRh0dt1K2vXNhAR3mLSV",
                (
                    r"next 4 January 2016 will be the commencement of trading",
                    r"new Class A shares will be Euro 0\.25 per share \(previously Euro 0\.50",
                ),
            ),
            Doc(
                "BME-hosted notice of warrant adjustment (BNP Paribas) for the Grifols split",
                "https://www.bolsasymercados.es/dam/descargas/indices/notices/"
                "adjustment-corporate-actions-warrants/ajuste-warrants-bnpp-grifols-split.pdf",
                (
                    r"ISIN: ES0171996012",
                    r"Fecha ExDate: 04/01/2016",
                    r"Split: 2x1",
                ),
            ),
        ),
        nominals=("0,50", "0,25"),
    ),
    TransitionSpec(
        key="FER-2023-merger",
        issuer="FERROVIAL",
        old_isin="ES0118900010",
        new_isin="NL0015001FS8",
        kind="CROSS_BORDER_MERGER",
        continuity="NEW_SECURITY",
        effective=date(2023, 6, 16),
        docs=(
            Doc(
                "BME-hosted notice of warrant underlying change (Societe Generale)",
                "https://www.bolsasymercados.es/dam/descargas/indices/notices/"
                "adjustment-corporate-actions-warrants/ferrovial-jun2023.pdf",
                (
                    r"absorci[oó]n de Ferrovial, S\.A\. por su filial Ferrovial International SE",
                    r"Ferrovial, S\.A\. ES0118900010 Ferrovial SE NL0015001FS8",
                    r"antes de la apertura de la sesi[oó]n del d[ií]a 16 de junio de 2023",
                ),
            ),
            Doc(
                "BME Instruccion Operativa 26/2023 (Internet Archive copy)",
                BME_IO + "2023/2023-26-IO-incorporacion-FER.pdf",
                (
                    r"Instrucci[oó]n Operativa N[ºo] 26/2023",
                    r"c[oó]digo ISIN NL0015001FS8",
                    r"bajo el c[oó]digo .FER.",
                    r"prevista para el d[ií]a 16 de junio",
                    r"precio de cierre de la sesi[oó]n anterior de FERROVIAL, S\.A\.",
                ),
                via="wayback",
                wayback_ts="20230717023409",
            ),
        ),
    ),
)

CODE_EVIDENCE: tuple[CodeEvidenceSpec, ...] = (
    CodeEvidenceSpec(
        key="FER-NL-code",
        code="FER",
        isin="NL0015001FS8",
        observed_on=date(2023, 6, 16),
        issuer="FERROVIAL SE",
        kind="BME_INSTRUCCION_OPERATIVA",
        doc=Doc(
            "BME Instruccion Operativa 25/2023 (Internet Archive copy)",
            BME_IO + "2023/2023-25-IO-incorporacion-FER.pdf",
            (
                r"Instrucci[oó]n Operativa N[ºo] 25/2023",
                r"c[oó]digo ISIN NL0015001FS8, se negociar[aá]n en el Sistema de Interconexi[oó]n "
                r"Burs[aá]til, modalidad de Contrataci[oó]n General, bajo el c[oó]digo .FER.",
                r"prevista para el d[ií]a 16 de junio",
            ),
            via="wayback",
            wayback_ts="20230614165043",
        ),
    ),
)
