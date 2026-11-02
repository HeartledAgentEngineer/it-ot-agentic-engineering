/*Versandunternehmen programmiert mit verketteten Listen*/
#include"versand_Header.h"
#include<stdio.h>
#include<stdlib.h>
#include<string.h>

int main(void)
{
	//////////////////////////////////////////////////////Variablen und Pointer-Deklaration
	
	
	produkt *pHeadP = NULL;		//Kopfpointer für Produktliste
	kunde *pHeadK = NULL;				//Kopfpointer für Kundenliste
	bestellung *pHeadB = NULL;
	char fileName[LEN] = { '\0' };                            // Name der geöffneten Datei
	FILE *pFile = NULL;                                      // file pointer der geöffneten Datei
	int change = 0;                                          // Daten geändert und nicht gespeichert?
	int aufstockung;
	char dateiauswahl;
	int menueauswahl;
	int PrdNr;
	int KundenNr;


	////////////////////////////////////////////////////////////////////////////
	printf("\nHAW Versand-AG\n");
	
	while (1)
	{
		menu();						//Aufruf der menu-Funktion -> Ausgabe des Menüs
		printf("Menuepunkt auswaelen:");
		scanf_s("%d", &menueauswahl);			//Einlesen der Menü-Auswahl und Zuweisung der Zahl zur Variablen menueauswahl
		printf("Menue-Auswahl: %d\n", menueauswahl);


		switch (menueauswahl)
		{

		case 1://neues Produkt eingeben
			printf("\nNeues Produkt eingeben:\n");
			printf("Bestell-Nummer:");
			scanf_s("%d", &PrdNr);
			produkt *pP = produktsuche(pHeadP, 1, PrdNr);		//Hilfspointer um Suchergebnis zu Speichern
			if (pP == NULL) 
			{
				pHeadP = neuesPrd(pHeadP, PrdNr);
			}
			
			else// Referenzierung auf Bezeichnung und Bestand + Aufstockung 
			{

				printf("%s ist schon mit %d Stueck am Lager.\n", pP->Bezeichnung, pP->Bestand);
				printf("Anzahl aufstocken:");
						scanf_s("%d", &aufstockung);
						pP->Bestand += aufstockung;
			}
			break;
		case 2:// Produktsuche
			produktsuche(pHeadP, 0, 0);
			break;
		case 3://produkte anzeigen
			
			produktlisteAnzeigen(pHeadP);
			break;
			
		case 4:
			printf("Kunden-Nummer: ");
			scanf_s("%i", &KundenNr); //Eingabe Kundennummer
			if (suchenachKundenNr(pHeadK, KundenNr) == NULL)
			{
				pHeadK = neuerKunde(pHeadK, KundenNr);
			}
			else
			{
				printf("Kunde schon vorhanden!\n");
			}
			
			break;
		case 5:
			kundenlisteAnzeigen(pHeadK);
			break;
		case 6:			//Bestellung aufgeben
			printf_s("Bestellung für welchen Kunden?\n");
			printf("Kunden-Nummer: ");
			scanf_s("%i", &KundenNr); //Eingabe Kundennummer
			kunde *pgefuKunde = suchenachKundenNr(pHeadK, KundenNr);
			if (pgefuKunde != NULL)
			{
				printf_s("Welches Produkt?\n");
				printf("Bestell-Nummer:");
				scanf_s("%d", &PrdNr);
				produkt *pP = produktsuche(pHeadP, 1, PrdNr);		//Hilfspointer um Suchergebnis zu Speichern
				if (pP != NULL)
				{
					pHeadB = neueBestellung(pHeadB, pP, pgefuKunde);
				}
				else
				{
					printf("Produkt nicht vorhanden!\n");
				}
			}
			else
			{
				printf("Dieser Kunde ist nicht vorhanden!\n");
			}
			break;

		case 7:

			printf("Kunden-Nummer: ");
			scanf_s("%i", &KundenNr); //Eingabe Kundennummer dessen Bestellungen angeszeigt werden sollen 

			if (suchenachKundenNr(pHeadK, KundenNr) != NULL)	//Kunde dessen Bestellungen man auflisten will, muss existieren  
			{
				ausgabeBestellungen(pHeadP, pHeadK, pHeadB, KundenNr);
			}
			else
			{
				printf("Kunde noch nicht vorhanden!");
			}
			break;
		case 8:			//Datei öffnen

			printf("Datei \x94 \bffnen\n");
			printf("Welche Datei? a: Produkte (*.prd) b: Kunden (*.cst) c: Bestellungen (*.ord)\n");
			printf("Datei-Auswahl: ");
			rewind(stdin);
			scanf_s("%c", &dateiauswahl, 1);

			switch (dateiauswahl)
			{
			case 'a':
				pHeadP = PrdListloeschen(pHeadP);
				pHeadP = produktlisteoeffnen();
				break;

			case 'b':
				pHeadK = KundenListloeschen(pHeadK);
				pHeadK = kundentlisteoeffnen();
				break;

			case 'c':
				
				break;

			default:
				break;
			}

			break;
		case 9:
			printf("Welche Datei? a: Produkte (*.prd) b: Kunden (*.cst) c: Bestellungen (*.ord)\n");
			printf("Datei-Auswahl: ");
			rewind(stdin);
			scanf_s("%c", &dateiauswahl, 1);
			switch (dateiauswahl)
			{
			case 'a':
				
				produktlistespeichern(pHeadP);
				break;

			case 'b':
				
				kundenlistespeichern(pHeadK);
				break;

			case 'c':
				
				
				break;

			default:
				break;
			}
			break;

		case 0:
			return 0;
			break;

		
		default:
			printf("Falsche Eingabe\n");
			break;

		}
	}
}