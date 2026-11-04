# Rebalanceamento global de EMC

## Objetivo

Auditar todos os itens descobertos no modpack, não apenas Mekanism Extras. A tabela mestra deve cobrir vanilla e todos os namespaces presentes nos mods instalados.

## Fonte de verdade e fluxo

1. Executar `gen_all.py` no ambiente local do modpack, com os JARs e tags da instalação.
2. O gerador continua escrevendo os valores carregados pelo ProjectE em `kubejs/data/emc_balanceado/pe_custom_conversions/00_valores_completos.json`.
3. O mesmo processo gera `kubejs/emc_fontes/00_tabela_mestra_emc.json`, com uma linha por item descoberto, inclusive itens sem EMC.
4. Revisar a tabela por namespace/mod, categoria e progressão; preencher `progression_tier`, `target_emc`, `review_status` e `review_notes`.
5. Revisar também `00_receitas_pendentes_emc.json`; receitas listadas não recebem custo automático até que seus insumos sejam modelados.
6. Só depois de revisar um grupo, transportar os valores aprovados para as fontes autorais em `kubejs/emc_fontes/` e regenerar o arquivo consumido pelo ProjectE.
7. Comparar os resultados, validar receitas reversíveis e cadeias de processamento, e testar no jogo antes de integrar.

## Critérios de balanceamento

- **Custo de obtenção:** ingredientes consumidos, quantidades, etapas e máquinas obrigatórias.
- **Progressão:** tecnologia, dimensão, estrutura, boss ou etapa necessária para obter o item.
- **Raridade e renovabilidade:** recurso comum, limitado, renovável, farmável ou exclusivo.
- **Hierarquia:** componentes equivalentes de tiers superiores devem custar mais que os inferiores, salvo justificativa explícita.
- **Cadeias de processamento:** nenhuma rota de conversão, compactação, descompactação ou processamento deve gerar EMC líquido.
- **Farms:** valor por item e rendimento por tempo precisam ser considerados em conjunto; itens renováveis não podem virar uma fonte desproporcional de EMC.
- **Exceções:** itens criativos, técnicos, de quest, de debug ou sem obtenção legítima devem permanecer sem EMC quando apropriado.

## Escala inicial

Âncoras atuais: ferro 256, ouro 2.048, diamante 8.192, nether star 139.264; Allthemodium 1.048.576, Vibranium 4.194.304, Unobtainium 16.777.216; estrela ATM 1 quintilhão (10^18). AllTheCompressed não recebe EMC, para não explodir pedra compactada nem puxar uniques para 64.

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

## Execução reproduzível

O gerador não presume um caminho pessoal de instalação. Informe a raiz do Minecraft/CurseForge por argumento ou variável de ambiente:

- Windows: `python -I gen_all.py "<instância ATM10>" "<pack_tags.json>" "<saída EMC.json>" "<bad_ids.txt>" --minecraft-root "<raiz Minecraft/CurseForge>"`
- Linux/macOS: use os mesmos argumentos, apontando `--minecraft-root` para a raiz equivalente da instalação.
- Para reconstruir o inventário sem reutilizar cache: acrescente `--no-cache`.
- Alternativamente, defina `ATM10_MINECRAFT_ROOT` (ou `MINECRAFT_ROOT`) e omita `--minecraft-root`.

O cache v2 é endereçado pelo SHA-256 do conjunto de entradas: JAR vanilla, JARs NeoForge e dos mods, arquivo de tags, JSONs de `kubejs/data`, lista de bloqueio e metadados da instância quando presentes. Inclusões, remoções ou alterações de conteúdo geram outra chave. O cache fica no diretório temporário do sistema e pode ser descartado com segurança. Cada execução também gera `00_metadados_geracao_emc.json`, registrando timestamp UTC, versões Minecraft/NeoForge, identidade do pack quando há manifesto, fingerprint SHA-256 e lista de arquivos usados.

## Qualidade e integração

- Toda correção do gerador deve ter teste automatizado reproduzível.
- Testes unitários devem cobrir receitas simples, múltiplas saídas, quantidades, chances, catalisadores, entradas probabilísticas e ciclos.
- Receitas com múltiplas saídas garantidas: enquanto não houver alocação de custo validada para co-produtos, cada saída recebe conservadoramente o custo integral dos insumos. Isso evita criar EMC por divisão artificial do custo, mas pode superestimar co-produtos; a política deve ser refinada com dados reais antes de revisar valores finais.
- Saídas com chance inferior a 100% ficam fora do cálculo automático até que o formato da receita tenha semântica probabilística explicitamente implementada. Saídas garantidas da mesma receita continuam sendo processadas.
- Receitas com entradas fluidas/químicas ainda não modeladas e layouts de ingredientes desconhecidos não entram no solver com custo parcial. O gerador deve listá-las em `00_receitas_pendentes_emc.json`, com ID, tipo e motivo, para revisão manual.
- Alterações de EMC precisam de comparação antes/depois e verificação de conservação nas rotas de craft, compactação e processamento.
- A integração é permitida após revisão do diff, execução bem-sucedida dos testes e validação dos dados gerados. Não integrar valores que ainda estejam pendentes.
- O responsável pelo projeto autorizou abrir PR e fazer merge quando esses critérios forem satisfeitos; isso não autoriza pular validações.

## Segurança das alterações

Todo o trabalho desta revisão fica na branch `balance/emc-global-rework-2026-11` até a validação. Não editar `main` diretamente. Valores ainda não revisados devem permanecer identificados como pendentes, em vez de receber números arbitrários.


## Diagnóstico de convergência do solver

Cada execução do solver registra o número de passadas e atualizações por fase/tier em `00_diagnostico_convergencia_emc.json`. Se qualquer tier atingir o limite de 80 passadas ainda alterando valores, o gerador interrompe a publicação do arquivo EMC final e aponta o relatório. Isso evita tratar uma solução parcial como resultado válido.

O relatório distingue apenas convergência e limite de iterações; ele não afirma, sozinho, que encontrou um ciclo específico. A identificação e correção da receita causadora ainda exige analisar os itens e dependências reportados. Testes sintéticos cobrem um ciclo estável e um ciclo de feedback positivo que não converge dentro do limite.


## Auditoria de saídas não interpretadas

Além das receitas pendentes por ingredientes, o gerador escreve `00_saidas_pendentes_emc.json` para receitas com uma chave de saída reconhecida pelo scanner, mas sem saída de item garantida interpretável. O relatório diferencia:
- `output_layout_unrecognized_or_non_item`: estrutura de saída ainda não suportada ou saída não é item;
- `output_items_not_in_pack_index`: ID de item foi lido, mas não está no índice de itens descobertos;
- `only_probabilistic_outputs`: a receita só apresenta saídas probabilísticas, que permanecem fora do cálculo automático.

O relatório não afirma que toda entrada pendente é uma falha: alguns formatos podem ser deliberadamente não-item. Ele cria uma fila verificável para ampliar o parser com fixtures reais, sem atribuir EMC indevido.
