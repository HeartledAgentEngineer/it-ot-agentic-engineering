#include"versand_Header.h"

void menu()
{
	printf("\n====================================\n");
	printf("1: Neues Produkt eingeben\n");
	printf("2: Produkt suchen\n");
	printf("3: Lagerbestand auflisten\n");
	printf("4: Neuen Kunden eingeben\n");
	printf("5: Kundenliste anzeigen\n");
	printf("6: Bestellung aufnehmen\n");
	printf("7: Bestellung eines Kunden auflisten \n");
	printf("8: Datei \x94 \bffnen.... \n");
	printf("9: Speichern unter... \n");
	printf("0: Ende\n");
	printf("====================================\n");
}

void drawline()
{
	printf("\n------------------------------------------------------------------------------------------");
}

int jaNein(char *text)
{
	char jn;
	printf("%s (j/n): ", text);
	rewind(stdin);
	jn = fgetc(stdin);
	rewind(stdin);
	return (jn == 'j') ? 1 : 0;
}

int FileExists(char *FileName) 
{
	FILE *pFile = fopen(FileName, "r");
	if (pFile==NULL)
	{
		return 0;
	}
	fclose(pFile);
	return 1;
}