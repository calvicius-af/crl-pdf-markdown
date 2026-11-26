# Aplicabilidade das verificações de auditoria

O recurso `perfis_auditoria.json` define uma política versionada. O catálogo RNC
fornece família, operação e âmbito; o nome canónico é o fallback explícito quando
não há uma correspondência única no catálogo. Um conflito de identidade não é
resolvido por aproximação.

| Perfil                               | Nota de depósito de convenção privada | Articulado próprio obrigatório                |
| ------------------------------------ | ------------------------------------- | --------------------------------------------- |
| Convenção privada                    | Sim                                   | Sim                                           |
| Alteração privada                    | Sim                                   | Não: pode publicar apenas alterações/tabelas. |
| Convenção pública                    | Não                                   | Sim                                           |
| Alteração pública                    | Não                                   | Não: pode publicar apenas alterações/tabelas. |
| Portaria, adesão, acórdão ou aviso   | Não                                   | Não: depende da natureza da publicação.       |
| Retificação, deliberação ou cessação | Não                                   | Não                                           |
| Desconhecido                         | Conservador: manter o controlo        | Conservador: manter o controlo                |

Não exigir articulado completo não elimina as verificações das cláusulas que
efetivamente existem. Um comando de eliminação publicado é conteúdo operativo,
não uma cláusula truncada. Introduções a alterações continuam a ser confrontadas
com o contexto e com a referência quando terminam em dois pontos.

Cobertura, ordem, valores, operadores, caracteres críticos, tabelas e integridade
dos artefactos continuam a ser verificados em todas as famílias. A política não
dispensa erros de conteúdo por o documento ser curto, público ou uma retificação.

Cada relatório regista perfil, origem do perfil, versão da política e impressão
digital do código/recursos usados. Alterações de regras requerem nova auditoria;
alterações de OCR ou modelos requerem extração compatível. Correções e resoluções
humanas pertencem à revisão do documento, não a este vocabulário global.
