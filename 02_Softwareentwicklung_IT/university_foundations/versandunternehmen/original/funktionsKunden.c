#include"versand_Header.h"

/* Funktion um neuen Kunden anzulegen
parameter: Nummernummer PrdNr
Rückgabe:  Pointer auf (Listenkopf) pH
*/
kunde *neuerKunde(kunde *pH, int PrdNr)
{
	kunde *pE;
	kunde *pAct = pH;
	pE = neuerKundEintrag(PrdNr);                                       // neues Element erzeugen, noch nicht in der Liste
	if (pH == NULL)
	{
		return pE;                         // Liste leer, Element wird Listenkopf
		KundeAnzeigen(pE);
	}
		while (pAct->pNext)                // Ende der Liste suchen
		pAct = pAct->pNext;
	pAct->pNext = pE;                    // neues Element hinten anhängen
	KundeAnzeigen(pE);
	return pH;										// Element wird als neuer Listenkopf eingefügt
	
}

/* Fkt neusPrdElem() erzeugt dynamisch ein neues Elementes, Dateneingabe durch Benutzer
   Parameter: Prd(Produktnummer)
   Rückgabewert: Pointer auf das neue Produkt-Element
*/
kunde *neuerKundEintrag(int KundenNr)
{
	kunde *pE = (kunde *)malloc(sizeof(kunde));	//Erzeugung eines neuen Speicherplatzes mit malloc inkl. Typumwandlung dieses erzeugten Pointers

	pE->KundenNr = KundenNr;

	rewind(stdin);
	printf("Vorname: "); scanf("%s", pE->Vorname);		//Eigangeaufforderung zur Eingabe des Kundenvornamens, Einlesen und Zuweisung(mit Pointern) der Eingabe als Bezeichnug des neu erzeugten Instanz 
	printf("Nachname: "); scanf("%s", pE->Nachname);		//Eigangeaufforderung zur Eingabe des Kundennachnamens, Einlesen und Zuweisung(mit Pointern) der Eingabe als Bezeichnug des neu erzeugten Instanz 
	pE->pNext = NULL;
	return pE;
}
kunde *suchenachKundenNr(kunde *pH , int KundenNr)
{
	kunde *pAct = pH;

	if (pH == NULL) return NULL;
	
	do			//einmal durch die Liste gehen
	{
		if (pAct->KundenNr == KundenNr)
		{
			return pAct;
		}
	} while (pAct->pNext);

	return NULL;
}
void kundenlisteAnzeigen(kunde *pH)
{
	kunde *pE;
	unsigned int i;
	printf("Die Liste enthaelt %d Kundeneintaege.\n", Kundzaelen(pH));
	drawline();
	printf("\n%4s%-15s%-20s%s"," ","Kunden-Nr.", "Vorname", "Nachname\n");
	for (i = 0, pE = pH; i < Kundzaelen(pH); i++)
	{
		printf("%3d ", i + 1);
		KundeAnzeigen(pE);
		pE = pE->pNext;                    // weiter durch die Liste gehen
	}
	drawline();
}
void KundeAnzeigen(kunde *pE)
{
	printf("%-15d%-20s%-20s\n", pE->KundenNr, pE->Vorname, pE->Nachname);
}

/* Kundzaelen() ermittelt die Anzahl der Listenelemente
	Parameter		Ptr auf Listenanfang
	Rückgabewert	Anzahl der Elemente
*/


unsigned int Kundzaelen(kunde *pH)
{
	unsigned int n = 0;                  // n Anzahl der Elem.
	if (pH == NULL) return 0;            // Liste leer
	do
	{
		n++;                               // zählen
		pH = pH->pNext;                    // Liste durchschreiten
	} while (pH != NULL);                // bis Ende erreicht
	return n;
}

void kundenlistespeichern(kunde *pH)
{
	char filename[LEN];
	FILE *pFile;
	printf("Dateiname (*.cst): "); scanf_s("%s", filename, LEN);
	if (FileExists(filename) && !jaNein("Datei existiert schon. Ueberschreiben? "))
		return;
	pFile = fopen(filename, "wb");                           // Datei zum Schreiben öffnen
	if (pFile)
	{
		kundendateischreiben(pFile, pH);
		fclose(pFile);
	}
	else
	{
		printf("Datei-Fehler");
	}
}
void kundendateischreiben(FILE *pFile, kunde *pH)
{
	kunde *pE = pH;                  // mit Listen-Kopf anfangen
	while (pE)                         // schreiben bis Listen-Ende erreicht ist
	{
		fwrite(pE, sizeof(kunde), 1, pFile); // Daten in Datei schreiben
		pE = pE->pNext;                    // weiter durch die Liste gehen
	}
	fclose(pFile);

}
kunde *kundentlisteoeffnen()
{
	kunde *pH = NULL;
	FILE *pFile = NULL;
	char filename[LEN];
	printf("Welche Datei soll geoeffnet werden (.cst)? ");
	scanf_s("%s", filename, LEN);
	pFile = fopen(filename, "rb");
	if (pFile)
	{
		pH = kundendateioeffnen(pFile);
	}
	else
	{
		printf("Datei nicht gefunden! \n");
		return NULL;                                           // leere Liste
	}
}
kunde *kundendateioeffnen(FILE *pFile)
{
	kunde *pH = NULL;
	kunde *pE = (kunde*)malloc(sizeof(kunde));
	while (fread(pE, sizeof(kunde), 1, pFile));
	{
		pE->pNext = NULL;
		pH = KundElemAnhaengen(pH, pE);
		pE = (kunde*)malloc(sizeof(kunde));
	}
	free(pE);                                                // am Ende das letzte, nicht benutzte Speicherobjekt wieder freigeben
	fclose(pFile);                                           // fertig, Datei schliessen
	printf("Es wurden %d Kundeneintraege eingeladen.\n", Kundzaelen(pH));
	return pH;
}
kunde *KundElemAnhaengen(kunde *pH, kunde *pE)
{
	kunde *pAct = pH;
	if (pH == NULL) return pE;         // List ist noch leer, neues Elem wird Listenanfang
	while (pAct->pNext)                // Ende der Liste suchen
		pAct = pAct->pNext;
	pAct->pNext = pE;                    // neues Element hinten anhängen
	return pH;
}
/* KundeListloeschen() löscht die komplette Liste, gibt den Speicher wieder frei
   Parameter		Ptr auf Listen-Kopf
   Rückgabewert	NULL-Ptr
*/
kunde *KundenListloeschen(kunde *pH)
{
	kunde *pE = pH;
	while (pH)
	{
		pE = pH;
		pH = pH->pNext;
		free(pE);
	}
	return NULL;
}