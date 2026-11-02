#include"versand_Header.h"

/* Funktion um neues Produkt einzugeben 
parameter: produktnummer PrdNr
Rückgabe:  Pointr auf (Listenkopf) pHeadP
*/
produkt *neuesPrd(produkt *pH ,int PrdNr)
{
	produkt *pE;
	produkt *pAct = pH;
	pE = neuerPrdEintrag(PrdNr);                                       // neues Element erzeugen, noch nicht in der Liste
	if (pH == NULL)
		return pE;                         // Liste leer, Element wird Listenkopf
	while (pAct->pNext)                // Ende der Liste suchen
		pAct = pAct->pNext;
	pAct->pNext = pE;                    // neues Element hinten anhängen
	return pH;										// Element wird als neuer Listenkopf eingefügt
	
}

/* Fkt neusPrdElem() erzeugt dynamisch ein neues Elementes, Dateneingabe durch Benutzer
   Parameter: Prd(Produktnummer)
   Rückgabewert: Pointer auf das neue Produkt-Element
*/
produkt *neuerPrdEintrag(int PrdNr)
{
	produkt *pE = (produkt *)malloc(sizeof(produkt));	//Erzeugung eines neuen Speicherplatzes mit malloc inkl. Typumwandlung dieses erzeugten Pointers

	pE->PrdNr = PrdNr ;
	
	printf("Bezeichnung: ");scanf_s("%s", pE->Bezeichnung,LEN);		//Eigangeaufforderung zur Eingabe der Bezeichnung, Einlesen und Zuweisung(mit Pointern) der Eingabe als Bezeichnug des neu erzeugten Instanz (Produkteintrags)
	rewind(stdin);
	printf("Preis: "); scanf_s("%lf", &(pE->Einzelpreis));			//Eigangeaufforderung zur Eingabe des Preieses, Einlesen und Zuweisung(mit Pointern) der Eingabe als Preis des neu erzeugten Instanz (Produkteintrags)
	printf("Anzahl: "); scanf_s("%i", &(pE->Bestand));				//Eigangeaufforderung zur Eingabe des Bestandes, Einlesen und Zuweisung(mit Pointern) der Eingabe als Bestand des neu erzeugten Instanz (Produkteintrags)
	pE->pNext = NULL;
	return pE;
 }


/*insertHeadPrd() fügt ein Element an den Anfang der Liste ein
	Parameter		Ptr auf Listenanfang, Ptr auf das einzufügende Element
	Rückgabewert	Ptr auf das eingefügte Element, das der Listenanfang werden muss
*/

produkt *insertHeadPrd(produkt *pH, produkt *pE)
{
	pE->pNext = pH;                      // alter Anfang wird Nachfolger von neuem Element
	return pE;                           // neues Element wid neuer Anfang 
}

/* appendPrdElem() hängt ein Element ans Ende der Liste an
   Parameter		Ptr auf Listenanfang, Ptr auf das einzufügende Element
   Rückgabewert	Ptr auf Listenanfang
*/
produkt *PrdElemAnhaengen(produkt *pH, produkt *pE)
{
	produkt *pAct = pH;
	if (pH == NULL) return pE;         // List ist noch leer, neues Elem wird Listenanfang
	while (pAct->pNext)                // Ende der Liste suchen
		pAct = pAct->pNext;
	pAct->pNext = pE;                    // neues Element hinten anhängen
	return pH;
}

/* Prdzaelen() ermittelt die Anzahl der Listenelemente
	Parameter		Ptr auf Listenanfang
	Rückgabewert	Anzahl der Elemente
*/

unsigned int Prdzaelen(produkt *pH)
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
/* searchByPos() sucht das Element mit der Position pos in der Liste, 1 ist die erste (Kopf)
   Parameter		Ptr auf Listenanfang, Position
   Rückgabewert	Pointer auf gefundenes Element, NULL im Fehlerfall
*/
produkt	*suchePrdnachPos(produkt *pH, unsigned int pos)
{
	produkt *pE = pH;
	unsigned int i;
	if (pos > Prdzaelen(pH) || pos < 1)
		return NULL;
	if (pos == 1)                       // pos 1 ist der Listen-Kopf!
		return pH;
	else                                 // nicht Listen-Kopf
	{
		i = 2;                             // beim 2. Element anfangen
		while (i <= pos)                 // das Element suchen
		{
			pE = pE->pNext;                  // weiter durch die Liste gehen
			i++;
		}
		return pE;
	}
}
void produktlisteAnzeigen(produkt *pH)
{
	produkt *pE;
	unsigned int i;
	printf("Die Liste enthaelt %d Eintraege.\n", Prdzaelen(pH));
	drawline();
	printf("\n%4s%-15s%-45s%-20s%s", " ","Produkt-Nr.", "Bezeichnung", "Preis", "Anzahl\n");
	for (i = 0, pE = pH; i < Prdzaelen(pH); i++)
	{
		printf("%3d ", i + 1);
		produktAnzeigen(pE);
		pE = pE->pNext;                    // weiter durch die Liste gehen
	}
	drawline();
}
void produktAnzeigen(produkt *pE)
{
	printf("%-15d%-45s%-20.2f%d\n", pE->PrdNr, pE->Bezeichnung, pE->Einzelpreis, pE->Bestand);
}

produkt *produktsuche(produkt *pH, int prdAbfrageDannEins, int prdNr)
{

	produkt E;                                             // Hilfselement für die Eingabe des Suchkriteriums
	produkt *pAct = pH;                                      // starten bei Listenanfang
	produkt *pGefunden = NULL;								 // gefundenes Element
	
	if (prdAbfrageDannEins==1)		// für Abfrage für die Erstellung eines neuen Produktes
	{
		if (pH == NULL)
		{
			return NULL;
		}
		do			//einmal durch die Liste gehen
		{
			if (pAct->PrdNr==prdNr)
			{
				return pAct;
			}
		} while (pAct->pNext);

		return NULL;
	}
	else
	{
		if (pH == NULL)
		{
			printf("Keine Produkte vorhanden.\n");
			return NULL;
		}
		
			printf("Suchen nach Produktnummer (1), Bezeichnung (2), Preis (3), Bestandsanzahl (4): ");
			int auswahl;
			scanf_s("%d", &auswahl);
			switch (auswahl)
			{
			case 1:
				printf("Suche nach Produktnummer: ");
				scanf_s("%d", &E.PrdNr);
				break;

			case 2:
				printf("Suche nach Bezeichnug: ");
				scanf_s("%s", &E.Bezeichnung, LEN);
				break;

			case 3:
				printf("Suche nach Preis: ");
				scanf_s("%lf", &E.Einzelpreis);
				break;

			case 4:
				printf("Suche nach Bestandszahl: ");
				scanf_s("%d", &E.Bestand);
				break;


			default:
				printf("Falsche Eingabe\n");
				break;
			}
			while (pAct)                                             // suchen bis nichts mehr gefunden
			{
				pGefunden = suchenach(pAct, &E, auswahl);
				if (pGefunden)                                            // Element gefunden
				{
					printf_s("%3d ", prdPosErmitteln(pH, pGefunden));           // lfd Nr ausgeben
					produktAnzeigen(pGefunden);                                 // einzelnen Datensatz anzeigen
					pAct = pGefunden->pNext;                                  // in der nächsten Runde nur hinter der Fundstelle suchen
				}

				else
					printf("Keine Produkte mit diesem Suchkriterium gefunden!\n");
					pAct = NULL;
			}
			
			return NULL;
		}
	
}
	produkt *suchenach(produkt *pH, produkt *pAct, int auswahl) 
	{
		if (pH == NULL) return NULL;
		switch (auswahl)                                       // pAct enthält das Suchkriterium in der relevanten Komponente
		{
		case 1:
			while (pH->pNext != NULL)
			{
				if (pH->PrdNr == pAct->PrdNr)
					return pH;                                       // gefunden
				pH = pH->pNext;                                    // weiter in der Liste
			} 
			if(pH->PrdNr == pAct->PrdNr)
				return pH;
			break;
		case 2:
			while (pH->pNext != NULL)
			{
				if (!strcmp(pH->Bezeichnung, pAct->Bezeichnung)) return pH;
				pH = pH->pNext;
			} 
			break;
			if (!strcmp(pH->Bezeichnung, pAct->Bezeichnung)) return pH;
		case 3:
			while (pH->pNext != NULL)
			{
				if (pH->Einzelpreis == pAct->Einzelpreis) return pH;
				pH = pH->pNext;
			} 
			if (pH->Einzelpreis == pAct->Einzelpreis) return pH;
			
			break;

		case 4:
			while (pH->pNext != NULL)
			{
				if (pH->Bestand == pAct->Bestand) return pH;
				pH = pH->pNext;
			} 
			if (pH->Bestand == pAct->Bestand) return pH;
			
			break;
		default:
			return NULL;

		}
		return NULL;
		
	}
	unsigned int prdPosErmitteln(produkt *pH, produkt *pE)
	{
		unsigned int pos = 1;
		if (pH == NULL || pE == NULL)
			return 0;                          // leere Liste oder kein Element
		while (pH != pE)                   // bei Übereinstimmung (=Fund) abbrechen
		{
			pH = pH->pNext;                    // durch die Liste gehen
			pos++;
		}
		if (pH != NULL)
			return pos;                        // Normalfall: Element gefunden
		else
			return 0;                          // Ende der Liste ohne Fund erreicht
	}
	void produktlistespeichern(produkt *pH) 
	{
		char filename[LEN];
		FILE *pFile;
		printf("Dateiname (*.prd): "); scanf_s("%s", filename, LEN);
		if (FileExists(filename) && !jaNein("Datei existiert schon. Ueberschreiben? "))
			return;
		pFile = fopen(filename, "wb");                           // Datei zum Schreiben öffnen
		if (pFile)
		{
			produktdateischreiben(pFile, pH);
			fclose(pFile);
		}
		else
		{
			printf("Datei-Fehler");
		}
	}
	void produktdateischreiben(FILE *pFile, produkt *pH) 
	{
		produkt *pE = pH;                  // mit Listen-Kopf anfangen
		while (pE)                         // schreiben bis Listen-Ende erreicht ist
		{
			fwrite(pE, sizeof(produkt), 1, pFile); // Daten in Datei schreiben
			pE = pE->pNext;                    // weiter durch die Liste gehen
		}
		fclose(pFile);

	}
	produkt *produktlisteoeffnen()
	{
		produkt *pH = NULL;
		FILE *pFile = NULL;
		char filename[LEN];
		printf("Welche Datei soll geoeffnet werden (.prd)? ");
		scanf_s("%s", filename, LEN);
		pFile = fopen(filename, "rb");
		if (pFile)
		{
			pH = produktdateioeffnen(pFile);
		}
		else
		{
			printf("Datei nicht gefunden! \n");
			return NULL;                                           // leere Liste
		}
	}
	produkt *produktdateioeffnen(FILE *pFile)
	{
		produkt *pH = NULL;
		produkt *pE = (produkt*) malloc(sizeof(produkt));			
		while (fread(pE, sizeof(produkt), 1, pFile));
		{
			pE->pNext = NULL;
			pH = PrdElemAnhaengen(pH, pE);
			pE = (produkt*)malloc(sizeof(produkt));
		}
		free(pE);                                                // am Ende das letzte, nicht benutzte Speicherobjekt wieder freigeben
		fclose(pFile);                                           // fertig, Datei schliessen
		printf("Es wurden %d Produkteintraege eingeladen.\n", Prdzaelen(pH));
		return pH;
	}
	/* PrdListloeschen() löscht die komplette Liste, gibt den Speicher wieder frei
   Parameter		Ptr auf Listen-Kopf
   Rückgabewert	NULL-Ptr
*/
	produkt *PrdListloeschen(produkt *pH)
	{
		produkt *pE = pH;
		while (pH)
		{
			pE = pH;
			pH = pH->pNext;
			free(pE);
		}
		return NULL;
	}


	