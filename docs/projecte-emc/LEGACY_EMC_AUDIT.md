# Auditoria estática da tabela histórica de EMC

**Data da auditoria:** 2026-10-17  
**Arquivo analisado:** `config/ProjectE/custom_emc.json`  
**Blob SHA observado:** `b46d57a57991c7b7f2005eb3d380a50869da1109`  
**Status:** auditoria estática inicial; não houve teste em runtime.

## Resultado executivo

A tabela contém 67.531 entradas com IDs únicos. A estrutura JSON foi lida integralmente pelo blob do GitHub; a leitura comum de arquivo devolvia conteúdo vazio por causa do tamanho, mas o blob confirma que o arquivo é grande. O arquivo permanece intacto em `main`, na branch de segurança e na branch de trabalho.

O fato de a tabela ser sintaticamente válida e não ter IDs duplicados **não demonstra que os preços estão balanceados**. Há sinais fortes de geração defeituosa ou de uma tabela inadequada para ser usada como economia final do modpack.

## Contagem e integridade

| Verificação | Resultado |
|---|---:|
| Entradas | 67.531 |
| IDs únicos | 67.531 |
| IDs duplicados encontrados | 0 |
| EMCs ausentes ou não numéricos | 0 |
| Valores negativos | 0 |
| Valores fracionários | 0 |
| Entradas com EMC = 1 | 638 |
| Entradas com EMC menor que 10 | 25.379 |
| Entradas com EMC >= 1.000.000 | 11.351 |
| Entradas com EMC >= 1.000.000.000 | 2.559 |
| Entradas com EMC >= 1.000.000.000.000 | 1.675 |
| Entradas exatamente no limite de inteiro assinado de 64 bits (9.223.372.036.854.775.807) | 35 |

Os valores muito grandes foram contados a partir dos dígitos originais do JSON, preservando a precisão inteira, em vez de usar arredondamento de ponto flutuante.

## Exemplos que precisam de revisão

**Estes são os valores atuais encontrados na tabela, não novos valores recomendados.** Precisam ser comparados com os mapeamentos nativos, receitas e progressão real do ATM10 antes de decidir se devem ser corrigidos.

| Item | EMC atual | Motivo para auditar |
|---|---:|---|
| `minecraft:stone` | 8 | Baseline de recurso básico |
| `minecraft:cobblestone` | 1 | Valor diferente do de pedra; confirmar receita e política |
| `minecraft:dirt` | 8 | Comparar com os demais recursos básicos |
| `minecraft:iron_ingot` | 8 | Valor muito baixo para um material de progressão; revisar |
| `minecraft:gold_ingot` | 2.048 | Revisar consistência com ferro, diamante e receitas |
| `minecraft:diamond` | 8.192 | Baseline de recurso avançado |
| `minecraft:emerald` | 8.192 | Mesmo EMC do diamante; confirmar se é intencional |
| `minecraft:netherite_ingot` | 8.194 | Quase igual ao diamante; revisar receitas e progressão |
| `minecraft:oak_log` | 1.000.000 | Recurso comum com valor extraordinariamente alto |
| `minecraft:oak_planks` | 1.000.000 | Tábuas com o mesmo valor do tronco; revisar ciclo de receita |
| `minecraft:obsidian` | 1 | Recurso de progressão com valor mínimo |
| `minecraft:ancient_debris` | 1 | Recurso raro com valor mínimo |
| `mekanism:pellet_polonium` | 8 | Subproduto avançado com valor mínimo |
| `mekanism:pellet_antimatter` | 8 | Subproduto avançado com valor mínimo |
| `mekanism:ingot_refined_obsidian` | 2.000.000.000.000 | Valor extremamente alto, exige revisão de cadeia produtiva |
| `productivetrees:advanced_wenge_beehive` | 1.000.000.000 | Valor extremo para auditar contra obtenção/receita |
| `mekanism_extras:infinite_energy_cube` | 403.008.957.595.613 | Item de energia com valor muito alto e risco de economia circular |

Além disso, 35 entradas estão exatamente em `9.223.372.036.854.775.807`, o maior inteiro assinado de 64 bits. Entre os exemplos estão vários blocos de compressão de níveis 5x a 9x de `allthecompressed`. O limite pode indicar saturação/overflow do algoritmo ou um teto artificial; isso exige revisão e não deve ser tratado como um preço de equilíbrio normal.

## Evidência ligada ao gerador antigo

O estado de resolução versionado na investigação anterior registrou:

- `knownProjectEValues: 0`
- `missingNormalItems: 67531`
- `recipeCount: 58610`
- `recipeSolvedEntries: 67531`
- `writtenEntries: 67531`

Essa contagem coincide com as 67.531 entradas da tabela. A evidência é compatível com a hipótese de que o gerador antigo calculou a tabela sem valores conhecidos de base do ProjectE. Isso não prova, por si só, qual valor correto cada item deveria ter, mas é motivo suficiente para não confiar cegamente no conjunto inteiro.

## Estratégia recomendada

1. **Não apagar nem substituir agora** as 67.531 entradas no arquivo ativo. O arquivo original continua preservado.
2. Corrigir primeiro a causa de os mapeamentos nativos do ProjectE não ficarem prontos.
3. Em uma cópia da instância, validar os valores nativos dos itens básicos e a Transmutation Table.
4. Criar uma lista de auditoria para itens suspeitos, agrupada por categoria e progressão.
5. Só depois propor overrides seletivos com IDs confirmados, justificativas e verificação de ciclos de receita.
6. Se for decidido abandonar a tabela gerada, manter uma cópia arquivada e fazer a troca por uma alteração revisável, com teste em runtime. Não substituir automaticamente por uma lista vazia.

## Limites

- Esta é uma análise de conteúdo estático; não comprova carregamento correto no jogo.
- Os valores citados são os valores existentes no arquivo, não os valores finais recomendados.
- Ainda não foi feito um recálculo completo das receitas nem análise de todos os ciclos possíveis.
- Nenhuma alteração de EMC foi feita neste relatório.
