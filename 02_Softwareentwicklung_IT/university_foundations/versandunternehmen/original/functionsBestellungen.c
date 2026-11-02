#include"versand_Header.h"
bestellung *neueBestellung(bestellung *pH, produkt *pP, kunde *pK) 
{
	bestellung *pE = (bestellung*)malloc(sizeof(bestellung));
	bestellung *pAct = pH;
	pE->KundenNr = pK->KundenNr;
	pE->PrdNr = pP->PrdNr;
	printf_s("Welche Anzahl soll bestellt werden?\n");
	printf_s("Bestellanzahl eingeben:");
	scanf_s("%d", &pE->Anzahl);
	if (pE->Anzahl <= pP->Bestand)
	{
		pE->Gesamtpreis = pE->Anzahl * pP->Einzelpreis;
		pP->Bestand -= pE->Anzahl;
		if (pH == NULL)
		{
			ausgabeNeueBestestellung(pP, pK, pE);
			return pE;                         // Liste leer, Element wird Listenkopf
		}
		while (pAct->pNext)                // Ende der Liste suchen
			pAct = pAct->pNext;
		pAct->pNext = pE;                    // neues Element hinten anhängen
		ausgabeNeueBestestellung(pP, pK, pE);
		return pH;										// Element wird als neuer Listenkopf eingefügt
	}
	else
	{
		pE = NULL;
		free(pE);
		printf("Nur %d %s am Lager.\n", pP->Bestand, pP->Bezeichnung);
		return pH;
	}
}
void ausgabeNeueBestestellung(produkt *produktptr, kunde *kundenptr, bestellung *ptr)
{
	printf("Neue Bestellung fuer %s %s", kundenptr->Vorname, kundenptr->Nachname);
	drawline();
	printf("\n%-15s|%-15s|%-30s|%-15s|%s", "Best-Nr", "Anzahl", "Bezeichnung", "Einz-Preis", "Ges-Preis");
	printf("\n%-15d|%-15d|%-30s|%-15.2f|%.2f", ptr->PrdNr, ptr->Anzahl, produktptr->Bezeichnung, produktptr->Einzelpreis, ptr->Gesamtpreis);
	drawline();
}
void ausgabeBestellungen(produkt *pHP, kunde *pHK, bestellung *pHB, int KundenNr)
{
	int i = 0;
	double gesamtsumme = 0;
	bestellung *pAct = pHB;
	kunde *kundenptr = suchenachKundenNr(pHK, KundenNr);// Kundensuche um auf den Namen referenzieren zu können
	printf("Bestellungen fuer %s %s", kundenptr->Vorname, kundenptr->Nachname);
	drawline();
	printf("\n%-15s|%-15s|%-30s|%-15s|%s", "Best-Nr", "Anzahl", "Bezeichnung", "Einz-Preis", "Ges-Preis");//Überschrift der Ausgabetabelle
	
	while ( pAct->pNext) 
	{
		if (pAct->KundenNr == KundenNr)//Überprügung des Bestelleintags auf die eingegebene Kundennummer
		{
			produkt *produktptr = produktsuche(pHP, 1, pAct->PrdNr);
			printf("\n%-15d|%-15d|%-30s|%-15.2f|%.2f", pAct->PrdNr, pAct->Anzahl, produktptr->Bezeichnung, produktptr->Einzelpreis, pAct->Gesamtpreis);//Ausgabe der Einzelnen Angaben dur referenzierung 
			gesamtsumme += pAct->Gesamtpreis;//Aufaddieren der Gesamtpreise der einzelnen Bestellungen
			pAct = pAct->pNext;
		}
	}
	drawline();
	printf("\n%-79s%.2f", "Gesamt-Summe", gesamtsumme);//formatirtre Ausgabe der Gesamtsumme
	drawline();

}