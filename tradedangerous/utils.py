# --------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
# Copyright (C) Bernd 'Gazelle' Gollesch 2016, 2017
# Copyright (C) Jonathan 'eyeonus' Jones 2018, 2019
#
# You are free to use, redistribute, or even print and eat a copy of
# this software so long as you include this copyright notice.
# I guarantee there is at least one bug neither of us knew about.
# --------------------------------------------------------------------
# TradeDangerous :: Modules :: Utils
#
"""This modules contains various utils to be used internally.
"""

import re

__all__ = ['titleFixup', 'checkForOcrDerp']

ocrDerp = re.compile(r'''(
    ^.$ |
    LAN[O0]ING |
    [O0][O0]CK |
    [O0]INEILL |
    AQUIRE[O0] |
    FNT[EF]RPRIS[EF] |
    [EF]NTFRPRIS[EF] |
    [EF]NT[EF]RPRISF |
    [O0](UTT|ALT)[O0]N |
    8RA[DO0]LEY |
    BRA[O0]LEY |
    LLOY[O0] |
    [O0]RBDAL |
    DRB[O0]DAL |
    [D0]RBITAL |
    REE[O0] |
    \BDOCK$ |
    \BTERMINAL\b |
    \bKID?[O0] |
    \b[O3]E\b |
    \bANDRA[O3]E\b |
    \bAN[O3]RADE\b |
    \bAN[O3]RA[O3]E\b |
    VVELL\b |
    [O0]IRAC\b |
    \bVV |
    \b[O0]ER?\b |
    \b[O0]RAKE |
    HAR[O0](T\b|W[I1L]CK) |
    ACQU[I1L]R[E3][O0] |
    \b[O0]ARK |
    \b[O0]DAM |
    [O0]EPOT |
    \bMERE[O0] |
    \b[O0]ENN?IS |
    \bBRAN[o0] |
    W[O0]{3} |
    GO(D[O0]|[O0]D|[O0][O])ARD |
    GO[DO0]{2}AR[O0] |
    ORB[RH]AL\b |
    \bJOR[O0]A |
    \bST[O0]ART |
    \bQUIMPY |
    \bVAR[O0]E |
    EN[^T]?ERPRISE |
    EN..ERPRISE |
    [E38]NT[E38]F[I1']?PR[I1'][S5][E38] |
    \bMUR[O0]O |
    \bBAR[O0]E |
    \bBALLAR[O0] |
    \b[O0]REYER\b |
    \bEDWAR[O0] |
    \bE[O0]WAR[DO0] |
    III |
    STARON\b |
    \bST.ION\b |
    \bSTION\b |
    \BHANG[EA]R$ |
    ^\S+HUB$ |
    \bLEBEOEV |
    \B(
        BASE |
        ENTE[RP]P[RP]ISE |
        TERMINA(L|II) |
        P(L|II)ANT |
        RELAY |
        ORBITAL |
        PLATFORM |
        COLONY |
        VISION |
        REFINERY
    )$ |
    [O0]RB[I1]DAL |
    [O0]R[DL][I1]TAL |
    \bBRIOGER |
    \bJUOSON |
    LANOER |
    G[O0][O0]([RW]|VV)[O0I]N |
    \bSPE([O0][DO0]|[DO0][O0])ING\b |
    \bARCHIMEOES\b |
    \bH[O0D]L[O0]ING |
    \bM[O0D]HMAN[O0] |
    \b[O0]ANA\b |
    \bALEKSAN[O0]R[O0D]V\b |
    \bCH[0D]MSKY\b |
    \b[O0]IESEL\b |
    [O0]{3} |
    SCHMI[O0]T |
    \bSAUN[O0]ER |
    [O0]IV[E3] |
    VIRIDN$ |
    \bHORI\.ONS |
    C[O0D]+LNY$ |
    \bR[O0]ZH[O0]E[S5]TVENSKY |
    \bRDZH[DO0]ESTVENSKY |
    '' |
    ^[^A-Z0-9] |
    \s{2,} |
    ^OEN |
    ^MCK(EF|FE)\b |
    \bCHAN\s+DLER |
    \b[O0]UMONT |
    \bUN[0O]ER |
    \bSDMM |
    \bREA([O0]D|D[O0]) |
    \bRD[DO0][DO0]EN |
    \bR[O0]([O0]D|D[O0])EN |
    (?<!BR)[O0]ECK$ |
    SE?TTL(FMENT|EMFNT|FMFNT) |
    SE?TTLMENT |
    STTL[E38]?M[E38]?NT |
    S\s?[E38]\s?T\s?T\s?L\s?[E38](\sM|M\s)[E38]\s?N\s?T$ |
    S[E38]TT[38]?L[E38]MNT |
    MARKFT |
    HANGFR |
    CL(EVF|FVE|FVF) |
    \bCRY$ |
    G[E3][D0]RG[E3]LUCA[S5] |
    PLAT[E3]F[D0]RM |
    OCONNOR |
    ` |
    -- |
    \bREILLI\b |
    \bRIN[FC]\b |
    \bOL[E3]ARY |
    \bSATION\b |
    ,\w |
    \bI?NGLY\b |
    \bAU\sL[DO0]\b |
    (^|\s)['.] |
    ^- | -$ |
    \bDREBBFL\b
    \bLEVIE |
    \bRN\b |
    \bH\sUNZIKER |
    \bL[O0D]FTH\sUS |
    \bHORNUCH\b |
    \bKLU\sDZE |
    ^[DR]HN\b |
    SU\sI?RVEY$ |
    H[DO0]L[O0]ING |
    H[D0]LDING |
    M[DO0]HMAN[O0] |
    \bABL\b |
    \bBENNET\b |
    \bHU8\b |
    \sCITV$ |
    \sPIT[VY]$ |
    \bTFR |
    IVII |
    \BINAI$ |
    SET[IT]''LEMEN |
    I'L | R'I | (^|\s)'L | [^Ss]'(?=\s|$) |
    ^I \s (?! [Ss][Oo][Ll][Aa]) |
    \bA7\S |
    \sH\sI?UB$ |
    \bALEDNDRIA\b |
    \sH\sU\sB$ |
    \bC[O0]LCNY\b |
    \bOOCTE\b |
    \bBULGAFIIN\b |
    \bWH\sIEEL |
    \bBR8NNAN\b |
    \b(ID)?ING$ |
    GATEVVAY$ |
    [HI\s]U\sI?B$ |
    CLAI\sI?M$ |
    \bUITY$ |
    \bDING$ |
    BTOP$ |
    B'I'OP$ |
    TRANQUNUTY$ |
    C[O0]LUNY$ |
    \bMAGN\sI?US\b |
    \s-[A-Z] |
    ^NAKAM(\sIU|U\sIR) |
    ^THOM\sI?PSON |
    ^STEPH\sI?ENSON |
    \bCQRK\b |
    ^AN\sI?DREW |
    ^WATSO\sIN |
    ^QSSW |
    ^RTZEN |
    \bI?NAL$ |
    \b''I\b
)''', flags=re.X)


def titleFixup(text):
    """
    Correct case in a word assuming the presence of titles/surnames,
    including 'McDonald', 'MacNair', 'McKilroy', and cases that
    python's title screws up such as "Smith's".
    """
    
    text = text.title()
    text = re.sub(
        r"\b(Mc)([a-z])",
        lambda match: match.group(1) + match.group(2).upper(),
        text
    )
    text = re.sub(
        r"\b(Mac)([bcdfgjklmnpqrstvwxyz])([a-z]{3,})",
        lambda m: m.group(1) + m.group(2).upper() + m.group(3),
        text
    )
    text = re.sub("\b(von|van|de|du|of)\b",
        lambda m: m.group(1).lower,
        text
    )
    text = re.sub(r"'S\b", "'s", text)
    text = ''.join((text[0].upper(), text[1:]))
    
    return text

def checkForOcrDerp(tdenv, systemName, stationName):
    match = ocrDerp.search(stationName.upper())
    if match:
        tdenv.NOTE(
            "Ignoring '{}/{}' because it looks like OCR derp."
            .format(systemName, stationName)
        )
        return match
    return None
