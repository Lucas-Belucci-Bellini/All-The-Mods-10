# Rebalanceamento global de EMC

## Objetivo

Auditar todos os itens descobertos no modpack, não apenas Mekanism Extras. A tabela mestra deve cobrir vanilla e todos os namespaces presentes nos mods instalados.

## Fonte de verdade e fluxo

1. Executar `gen_all.py` no ambiente local do modpack, com os JARs e tags da instalação.
2. O gerador continua escrevendo os valores carregados pelo ProjectE em `kubejs/data/emc_balanceado/pe_custom_conversions/00_valores_completos.json`.
3. O mesmo processo gera `kubejs/emc_fontes/00_tabela_mestra_emc.json`, com uma linha por item descoberto, inclusive itens sem EMC.
4. Revisar a tabela por namespace/mod, categoria e progressão; preencher `progression_tier`, `target_emc`, `review_status` e `review_notes`.
5. Só depois de revisar um grupo, transportar os valores aprovados para as fontes autorais em `kubejs/emc_fontes/` e regenerar o arquivo consumido pelo ProjectE.
6. Comparar os resultados, validar receitas reversíveis e cadeias de processamento, e testar no jogo antes de integrar.

## Critérios de balanceamento

- **Custo de obtenção:** ingredientes consumidos, quantidades, etapas e máquinas obrigatórias.
- **Progressão:** tecnologia, dimensão, estrutura, boss ou etapa necessária para obter o item.
- **Raridade e renovabilidade:** recurso comum, limitado, renovável, farmável ou exclusivo.
- **Hierarquia:** componentes equivalentes de tiers superiores devem custar mais que os inferiores, salvo justificativa explícita.
- **Cadeias de processamento:** nenhuma rota de conversão, compactação, descompactação ou processamento deve gerar EMC líquido.
- **Farms:** valor por item e rendimento por tempo precisam ser considerados em conjunto; itens renováveis não podem virar uma fonte desproporcional de EMC.
- **Exceções:** itens criativos, técnicos, de quest, de debug ou sem obtenção legítima devem permanecer sem EMC quando apropriado.

## Escala inicial

Os valores existentes servem apenas como âncoras iniciais, não como verdade imutável: ferro 256, ouro 2.048, diamante 8.192; Allthemodium 32.768, Vibranium 65.536 e Unobtainium 131.072. A auditoria pode ajustar esses números se a progressão real do pack justificar.

## Campos da tabela mestra

| Campo | Significado |
|---|---|
| `id` | ID completo do item (`namespace:item`) |
| `mod` | Namespace responsável |
| `current_emc` | Valor calculado atualmente; nulo se não houver EMC |
| `origin` | Origem do valor: base manual, regra de minério, heurística ou receita |
| `progression_tier` | Tier de progressão a ser atribuído na revisão |
| `target_emc` | Valor proposto após auditoria |
| `review_status` | `pending`, `reviewed`, `approved` ou `exception` |
| `review_notes` | Justificativa, dependências e exceções |

## Ordem de auditoria

1. Materiais e componentes de progressão (metais, gemas, ligas, circuitos e peças).
2. Mekanism, Mekanism Extras e demais linhas de máquinas por tier.
3. Recursos de dimensões, bosses e estruturas.
4. Itens de processamento, química, energia e armazenamento.
5. Agricultura, drops, recursos renováveis e farms.
6. Itens de todos os demais mods e conteúdo vanilla.
7. Auditoria final de receitas, conversões e balanceamento por hora de farm.

## Segurança das alterações

Todo o trabalho desta revisão fica na branch `balance/emc-global-rework-2026-11`. Não alterar `main`, não abrir PR nem fazer merge automaticamente. Valores ainda não revisados devem permanecer identificados como pendentes, em vez de receber números arbitrários.
