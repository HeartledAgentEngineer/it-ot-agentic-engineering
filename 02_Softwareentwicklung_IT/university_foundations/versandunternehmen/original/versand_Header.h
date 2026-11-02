
#define _CRT_SECURE_NO_WARNINGS
#include<stdio.h>
#include<stdlib.h>
#include<string.h>

#define LEN 20
#define NO_NL(a) a[strlen(a)-1]='\0'                       // löscht '\n' am Ende des Strings
#define SWAP_I(a,b) {int tmp=(a); (a)=(b); (b)=tmp;}       // vertauscht 2 int


//Deklaration des structs vom Typ produkt
typedef struct Produkt
{
	int PrdNr;
	char Bezeichnung[30];
	double Einzelpreis;
	int Bestand;
	struct Produkt *pNext;
} produkt;

//Deklaration des structs vom Typ Kunde
typedef struct Kunde
{
	int KundenNr;
	char Vorname[30];
	char Nachname[30];
	struct Kunde *pNext;	
} kunde;

//Deklaration des structs vom Typ Bestelllung
typedef struct Bestelllung
{
	int KundenNr;
	int PrdNr;
	int Anzahl;
	double Gesamtpreis;
	struct bestellung *pNext;
} bestellung;

//Allgemeine Funktionen
void menu();
void drawline();
int jaNein(char *text);
int FileExists(char *FileName);

//Produkt Funktionen///////////////////////////////////

produkt *neuesPrd(produkt *pH, int PrdNr);
produkt *neuerPrdEintrag(int PrdNr);
produkt *insertHeadPrd(produkt *pH, produkt *pE);
produkt *PrdElemAnhaengen(produkt *pH, produkt *pE);
unsigned int Prdzaelen(produkt *pH);
produkt	*suchePrdnachPos(produkt *pH, unsigned int pos);
void produktlisteAnzeigen(produkt *pH);
void produktAnzeigen(produkt *pE);
produkt *produktsuche(produkt *pH, int prdAbfrageDannEins, int prdNr);
produkt *suchenach(produkt *pH, produkt *pAct, int auswahl);
unsigned int prdPosErmitteln(produkt *pH, produkt *pE);
produkt *PrdListloeschen(produkt *pH);

void produktlistespeichern(produkt *pH);
void produktdateischreiben(FILE *pFile, produkt *pH);

produkt *produktlisteoeffnen();
produkt *produktdateioeffnen(FILE *pFile);
///////////////////////////////////////////////////////////////


//Kundenfunktionen//////////////////////////////////////
kunde *neuerKunde(kunde *pH, int PrdNr);
kunde *neuerKundEintrag(int KundenNr);
kunde *suchenachKundenNr(kunde *pH, int KundenNr);
unsigned int Kundzaelen(kunde *pH);
void kundenlisteAnzeigen(kunde *pH);
void KundeAnzeigen(kunde *pE);

void kundenlistespeichern(kunde *pH);
void kundendateischreiben(FILE *pFile, kunde *pH);

kunde *kundentlisteoeffnen();
kunde *kundendateioeffnen(FILE *pFile);
kunde *KundElemAnhaengen(kunde *pH, kunde *pE);
kunde *KundenListloeschen(kunde *pH);

//Bestellungsfunktionen///////////////////////////////////
bestellung *neueBestellung(bestellung *pH, produkt *pP, kunde *pK);
void ausgabeNeueBestestellung(produkt *produktptr, kunde *kundenptr, bestellung *ptr);
void ausgabeBestellungen(produkt *pHP, kunde *pHK, bestellung *pHB, int KundenNr);