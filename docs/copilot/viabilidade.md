# Documentos do BTE como recursos de agentes Microsoft Copilot

## Conclusão e âmbito

Os PDFs do BTE e os textos preparados por este projeto podem alimentar fontes de
conhecimento de agentes. A recolha, conversão e auditoria devem correr previamente
num ambiente Python. O agente consulta o corpus aprovado e aplica instruções de
análise; a recuperação de informação não substitui a auditoria documental.

A documentação oficial consultada em 6 de outubro de 2026 já descreve **custom
skills em preview** para agentes declarativos. A disponibilidade no tenant do II
não foi verificada: exige inscrição no Microsoft Frontier Program e licença
qualificada ou acesso pay-as-you-go. Skills não estão disponíveis em tenants com
Microsoft Purview Information Barriers. A ausência do botão não demonstra ausência
da funcionalidade em todas as versões do Copilot.

## Caminhos possíveis

| Plataforma disponível no II             | Caminho para os documentos                                           | Caminho para o procedimento                                                    |
| --------------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| Copilot Chat sem criação de agentes     | Anexar um pequeno conjunto de ficheiros por conversa, se permitido   | Fornecer instruções na conversa; confirmar as capacidades da licença           |
| Microsoft 365 Copilot com Agent Builder | Fontes SharePoint/OneDrive ou ficheiros incorporados                 | Instruções do agente; skill apenas se a preview estiver disponível             |
| Copilot Studio                          | Fontes de conhecimento; confirmar conectores e políticas do ambiente | Tópicos, ferramentas e fluxos, incluindo Power Automate conforme licenciamento |
| Agent Builder com skills Frontier       | Preferir corpus em SharePoint e procedimento na skill                | Upload de ZIP com `SKILL.md` e recursos; testar no tenant                      |

O caminho recomendado para um corpus que muda é uma biblioteca SharePoint
reservada aos documentos aprovados. Um carregamento manual de ficheiros serve
para um piloto pequeno. Para atualizar o corpus automaticamente, avaliar um fluxo
externo aprovado pelo II que invoque a recolha/conversão e publique os resultados.
Essa publicação e as credenciais Microsoft não foram implementadas neste fork.

## Formatos, limites e acesso

A tabela oficial de conhecimento do Agent Builder enumera PDF, DOC/DOCX, TXT,
PPT/PPTX e XLS/XLSX; HTML apenas em SharePoint. **Markdown não aparece nessa
tabela**: não assumir que o `.md` gerado é aceite como fonte de conhecimento.
Usar os PDFs originais com camada textual ou preparar TXT/DOCX a partir do Markdown
aprovado, conservando títulos, marcadores legais e tabelas. Mudar a extensão de
um Markdown para TXT mantém a sintaxe; validar a leitura e as citações no piloto.

Os limites publicados do Agent Builder são 20 ficheiros incorporados, 100 ficheiros
SharePoint, 50 OneDrive e quatro URLs públicas por agente. Os limites de ficheiros
incorporados são 512 MB para PDF/DOCX/TXT/PPTX e 30 MB para XLS/XLSX. Estes números
referem-se ao Agent Builder, não devem ser transpostos para Copilot Studio nem
tratados como garantia de recuperação de todo o conteúdo.

As fontes SharePoint/OneDrive respeitam permissões e rótulos existentes. Ficheiros
incorporados disponibilizam o seu conteúdo a quem acede ao agente, sujeitos às
restrições dos rótulos: rever o público do agente antes da partilha. O corpus BTE
é público; os pareceres ou notas internas associados podem ter outro regime.

## Skills: o que pode realmente correr

O Agent Builder aceita até oito skills, cada ZIP até 50 MB, ficheiros até 25 MB,
até 350 ficheiros no conjunto de skills, profundidade de diretórios até três e
instruções de `SKILL.md` com menos de 20 000 caracteres. Os recursos de skills
aceitam `.md`, `.pdf`, `.txt`, `.json`, `.xlsx` e outros formatos documentados.
Isto é uma lista distinta da lista de formatos das fontes de conhecimento.

Os scripts de skills não têm rede, não podem instalar pacotes nem fazer chamadas
autenticadas. Só podem usar pacotes já presentes, cuja disponibilidade tem de ser
confirmada. Portanto, não empacotar `recolha.py` ou Docling esperando que possam
descarregar PDFs ou modelos dentro do Copilot. Ferramentas e conectores habilitados
podem ser usados pelo orquestrador do agente, fora do sandbox dos scripts.

A preview também indica que skills e **ficheiros incorporados** ainda não podem
ser combinados no mesmo agente. Para esse caminho, usar fontes SharePoint e
confirmar o funcionamento no tenant, ou escolher um piloto só com instruções e
ficheiros incorporados. O pacote proposto abaixo contém apenas o procedimento e
um modelo de resposta; não inclui o corpus nem scripts de recolha.

## Preparação e piloto propostos

1. Obter os índices DGERT e executar `collect` conforme o README. Guardar o Excel,
   o PDF original e `registo_bte.jsonl` para manter a proveniência.
2. Executar `convert`. Consultar `_auditoria/diagnostico.md` e os relatórios
   individuais. `passed` significa ausência de alertas automáticos, não aprovação
   jurídica; `review` e `blocked` exigem revisão antes de alimentar o agente.
3. Selecionar inicialmente cinco documentos conferidos. Preservar no catálogo o
   ID DGERT, ano/número BTE, tipo, código IRCT, título, outorgantes, ligação oficial,
   hash do PDF e estado de revisão. Não afirmar vigência só com base na publicação.
4. Colocar apenas documentos aprovados na biblioteca usada pelo agente. Conservar
   auditorias numa localização separada para que não sejam recuperadas como normas.
5. Adicionar as fontes no Agent Builder e esperar que estejam prontas. Copiar as
   instruções de `instrucoes-agente.txt`; se houver acesso Frontier, experimentar
   a skill em `skill-bte/` num agente compatível sem ficheiros incorporados.
6. Testar cláusulas, alíneas, montantes, tabelas, alterações e perguntas sem resposta.
   Confirmar as citações abrindo a fonte. Não presumir que um índice completo foi
   lido nem que uma resposta sem resultado prova inexistência de disposição.

Critérios do piloto: cláusula e documento certos; montantes e unidades corretos;
nenhuma mistura entre versões; fonte verificável para cada afirmação documental;
recusa de inferir vigência ou cobertura não demonstradas. Testar também utilizadores
com e sem acesso à biblioteca. Para pesquisas exaustivas ou cálculos salariais,
usar extração estruturada e validação determinística fora da busca semântica.

O pacote é um protótipo de instruções, não uma integração executada no II. Não
foram usados credenciais, documentos internos ou serviços Microsoft do utilizador.

## Empacotar a skill proposta

A pasta da skill é versionada; o ZIP é um resultado gerado e não entra no Git.
A partir da raiz do repositório, usar a biblioteca padrão Python:

```bash
mkdir -p results/copilot
(cd docs/copilot/skill-bte && python -m zipfile -c ../../../results/copilot/consulta-bte.zip SKILL.md references)
python -m zipfile -t results/copilot/consulta-bte.zip
```

O ZIP tem `SKILL.md` na raiz e o modelo em `references/`. Não carregar `SKILL.md`
isoladamente. O empacotamento local não demonstra aceitação nem execução no II.

## Fontes oficiais e evidência consultada

Na primeira consulta, as páginas Learn e o site BTE devolveram HTTP 403 neste
ambiente. Após a atualização da rede, a descarga real do BTE foi validada. A documentação
Microsoft foi lida no seu repositório oficial `MicrosoftDocs/m365copilot-docs`,
commit `70e1e3f2b14ae1557439f175c01f74da42cfef6f`. As referências abaixo permitem
verificar os limites e a disponibilidade; as condições podem mudar após a preview.

- [Fontes de conhecimento no Agent Builder](https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/agent-builder-add-knowledge)
- [Adicionar skills no Agent Builder](https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/agent-builder-add-skills)
- [Skills: suporte, sandbox e limites](https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/declarative-agent-skills)
- [Fonte oficial das skills no GitHub](https://github.com/MicrosoftDocs/m365copilot-docs/blob/70e1e3f2b14ae1557439f175c01f74da42cfef6f/docs/declarative-agent-skills.md)
- [Fonte oficial do conhecimento no GitHub](https://github.com/MicrosoftDocs/m365copilot-docs/blob/70e1e3f2b14ae1557439f175c01f74da42cfef6f/docs/agent-builder-add-knowledge.md)
- [Recolha original do AppCCT](https://github.com/calvicius-af/crl-app-cct/blob/9faa8fef3c73d4a853e0c2f6592ce69ac42b7709/cct/recolha.py)
