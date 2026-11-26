# Testar o CRL sem internet

Este pacote é uma versão de teste para o sistema/Python indicados em `pacote.json`.
Inclui a aplicação, todas as bibliotecas e os modelos locais. Conserve a pasta
completa. O pacote Windows de teste usa Python **3.13, 64 bits, com Tcl/Tk**;
se esse Python ainda não estiver instalado, peça ao apoio informático.

1. Descarregue o ZIP completo e extraia-o para uma pasta. Não execute ficheiros
   diretamente dentro do ZIP. Depois da descarga, pode desligar a rede.
2. Faça duplo clique em **Instalar_CRL.bat**. Não precisa de administrador.
   Aguarde: a cópia e instalação das bibliotecas/modelos pode demorar vários minutos.
3. A instalação só termina depois de verificar os ficheiros, as dependências,
   a interface gráfica e uma conversão com modelos locais e rede bloqueada.
   Aguarde a mensagem **Instalação concluída**.
4. Abra **Abrir_CRL.bat** no caminho indicado na janela, normalmente
   `%LOCALAPPDATA%\CRL-PDF-Markdown`. Os modelos e o modo offline ficam selecionados.
5. Comece pelo `smoke.pdf` incluído no pacote, com uma **pasta de saída nova**.
   Abra o relatório e confira o título, as categorias e os valores da tabela.
6. Teste depois um PDF seu pequeno, novamente numa pasta nova. Confira títulos,
   números, tabelas e o relatório. Não substitua documentos já codificados no MAXQDA.

Reinstalar conserva o ambiente anterior e só publica o novo lançador depois do
ensaio passar. Os originais, correções e decisões do corpus não são migrados nem
substituídos pela instalação.

Se falhar, conserve os ficheiros da pasta **assistencia** indicada na janela.
Entregue ao apoio apenas o relatório Markdown e o TXT da operação, sem PDFs pessoais.
O guia **INSTALACAO_E_AJUDA.md** explica caminhos de rede e erros de instalação.

Se a mensagem indicar que não existe alias curto para um caminho com acentos,
o apoio deve escolher uma pasta **local, sem acentos e com permissão de escrita**:

```powershell
py -3.13 instalar_offline.py --destination "C:\CRL-Teste"
```

Não é necessário renomear o utilizador Windows, alterar modelos ou instalar
bibliotecas manualmente. Não misture ficheiros de pacotes diferentes.

Para registar o teste, guarde a versão de `pacote.json`, a versão do Python,
o resultado da instalação, se a janela abriu, o PDF de ensaio usado e o resultado
da conferência. Alertas de qualidade de documentos continuam a exigir revisão;
a instalação concluída não aprova automaticamente um corpus.
