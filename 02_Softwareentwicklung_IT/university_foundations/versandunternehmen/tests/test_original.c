/* Characterization tests for the 2020 student code in ../original (written 2026).
 *
 * They call the original list and file functions directly - no menu, no keyboard input -
 * and pin down how the code really behaves, including the bugs listed in REVIEW-2026.md.
 * A test named "bug_..." passes when the bug is still there; the original stays unchanged.
 * Bugs that end in an endless loop (B1, B5) are not executed here, only documented.
 *
 * Exit code = number of failed checks (0 = all green).
 */
#include "versand_Header.h"

static int fehler = 0;

#define PRUEFE(bedingung, text)                                    \
    do {                                                           \
        if (bedingung) printf("  ok    %s\n", text);               \
        else { printf("  FAIL  %s\n", text); fehler++; }           \
    } while (0)

static produkt *neu(int nr, const char *name, double preis, int bestand)
{
    produkt *p = (produkt *)calloc(1, sizeof(produkt));
    p->PrdNr = nr;
    strncpy(p->Bezeichnung, name, sizeof(p->Bezeichnung) - 1);
    p->Einzelpreis = preis;
    p->Bestand = bestand;
    return p;
}

static produkt *drei_produkte(void)
{
    produkt *pH = NULL;
    pH = PrdElemAnhaengen(pH, neu(4239, "Computer", 698.50, 20));
    pH = PrdElemAnhaengen(pH, neu(8238, "Monitor", 263.95, 100));
    pH = PrdElemAnhaengen(pH, neu(4257, "Printer", 93.70, 37));
    return pH;
}

static void test_liste_aufbauen_und_zaehlen(void)
{
    produkt *pH = drei_produkte();
    PRUEFE(Prdzaelen(pH) == 3, "append three products -> list counts 3");
    PRUEFE(Prdzaelen(NULL) == 0, "empty list counts 0");
    PrdListloeschen(pH);
}

static void test_position(void)
{
    produkt *pH = drei_produkte();
    PRUEFE(suchePrdnachPos(pH, 2)->PrdNr == 8238, "position 2 is the second product");
    PRUEFE(suchePrdnachPos(pH, 0) == NULL && suchePrdnachPos(pH, 4) == NULL,
           "positions outside the list return NULL");
    PRUEFE(prdPosErmitteln(pH, pH->pNext->pNext) == 3, "third element has position 3");
    PrdListloeschen(pH);
}

static void test_suche_nach_nummer(void)
{
    produkt *pH = drei_produkte();
    produkt kriterium = {0};
    PRUEFE(produktsuche(pH, 1, 4239) == pH, "lookup used by menu 1 finds the head element");
    kriterium.PrdNr = 4257;
    PRUEFE(suchenach(pH, &kriterium, 1) == pH->pNext->pNext, "search by number finds the last element");
    PrdListloeschen(pH);
}

static void test_bug_b3_name_suche_verfehlt_letztes(void)
{
    produkt *pH = drei_produkte();
    produkt kriterium = {0};
    strcpy(kriterium.Bezeichnung, "Monitor");
    PRUEFE(suchenach(pH, &kriterium, 2) == pH->pNext, "search by name finds a middle element");
    strcpy(kriterium.Bezeichnung, "Printer");
    PRUEFE(suchenach(pH, &kriterium, 2) == NULL,
           "bug_B3: search by name never finds the LAST element ('break' before the last check)");
    PrdListloeschen(pH);
}

static void test_bug_b2_laden_liest_nur_einen_datensatz(void)
{
    const char *datei = "test_roundtrip.prd";
    produkt *pH = drei_produkte();
    produkt *geladen;
    FILE *f = fopen(datei, "wb");
    produktdateischreiben(f, pH);          /* closes the file itself (see B6) */
    f = fopen(datei, "rb");
    geladen = produktdateioeffnen(f);      /* reads and closes */
    PRUEFE(Prdzaelen(geladen) == 1,
           "bug_B2: saving 3 products and loading them back yields only 1 (';' after while)");
    PrdListloeschen(pH);
    PrdListloeschen(geladen);
    remove(datei);
}

static void test_kunde_suchen(void)
{
    kunde *k = (kunde *)calloc(1, sizeof(kunde));
    k->KundenNr = 3942;
    PRUEFE(suchenachKundenNr(k, 3942) == k, "customer lookup finds the head element");
    PRUEFE(suchenachKundenNr(NULL, 1) == NULL, "customer lookup on empty list returns NULL");
    KundenListloeschen(k);
}

int main(void)
{
    printf("Characterization tests: Versandunternehmen (2020)\n");
    test_liste_aufbauen_und_zaehlen();
    test_position();
    test_suche_nach_nummer();
    test_bug_b3_name_suche_verfehlt_letztes();
    test_bug_b2_laden_liest_nur_einen_datensatz();
    test_kunde_suchen();
    printf("%d check(s) failed\n", fehler);
    return fehler;
}
