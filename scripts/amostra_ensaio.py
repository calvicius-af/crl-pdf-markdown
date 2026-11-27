"""Amostra pequena de PDF para o ensaio de ponta a ponta no instalador.

Escreve PDF sintéticos (sem dados de trabalho) que exercitam os caminhos da
revisão: um documento sem alertas, um com sinais negativos e uma tabela, e
copia o PDF de teste incluído no instalador. Nomes longos, como os do BTE.
"""
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.pdf_sintetico import escrever_pdf, grelha, pagina_bte  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--saida', type=Path, required=True)
    parser.add_argument('--smoke', type=Path, help='smoke.pdf do instalador')
    args = parser.parse_args()
    folder = args.saida / 'APU'
    folder.mkdir(parents=True, exist_ok=True)
    escrever_pdf(folder / '2026_BTE_03_APU_034_ACT_ACEP1-2026_FreguesiaVilaNova-STAL.pdf', [pagina_bte(1, [
        'Acordo coletivo de empregador público', 'Cláusula 1.ª', 'Âmbito',
        'O presente acordo aplica-se aos trabalhadores da freguesia.',
        'Depositado em 15 de janeiro de 2026.'])])
    tabela = [*pagina_bte(1, ['Acordo de empresa', 'Anexo I', 'Tabela salarial',
                              'O saldo da conta é -500,00 euros, entre -8 e -14 dias.']),
              *grelha(72, 560, [200, 120], [16, 16, 16]),
              (76, 596, 'Categoria'), (276, 596, 'Retribuição'),
              (76, 580, 'Técnico superior'), (276, 580, '1 250,00'),
              (76, 564, 'Assistente técnico'), (276, 564, '-950,00')]
    escrever_pdf(folder / '2026_BTE_11_APU_112_ACT_ACEP13-2026_FreguesiaNossa-STAL.pdf',
                 [tabela, pagina_bte(2, ['Cláusula 2.ª', 'Vigência', 'Entra em vigor no dia seguinte.'])])
    if args.smoke:
        shutil.copy2(args.smoke, args.saida / 'smoke.pdf')


if __name__ == '__main__':
    main()
