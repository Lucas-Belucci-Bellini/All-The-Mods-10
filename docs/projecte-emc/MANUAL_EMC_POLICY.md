# Política de trabalho para balanceamento manual de EMC

## Princípio de segurança

**Não substituir nem esvaziar a tabela ativa de EMC inteira para começar do zero.** O arquivo `config/ProjectE/custom_emc.json` na base atual é grande; a leitura simples do conector não devolve seu conteúdo completo, mas o diff do Git confirma que ele contém uma tabela histórica extensa. Essa tabela precisa ser preservada até que seja inspecionada e comparada de forma confiável.

A branch `safety/pre-manual-emc-balancing-2026-10-17` é o ponto de recuperação. A branch `work/manual-emc-balancing` é onde os próximos passos serão preparados. Nenhuma delas deve ser integrada automaticamente em `main`.

## Objetivo de balanceamento

Manter o ProjectE como motor de EMC e preservar mapeamentos nativos quando funcionarem. Alterar manualmente apenas os valores que exigirem ajuste de progressão, exceção comprovada ou correção de um valor inadequado.

Não presumir que os valores legados estão certos, mas também não removê-los em massa sem auditoria e testes: isso pode mudar drasticamente a economia do mundo e o comportamento da Transmutation Table.

## Formato documentado para uma entrada

O formato de override utiliza `id` ou `tag` e um `emc` inteiro não negativo. Exemplo ilustrativo, não um valor recomendado:

```json
{
  "id": "namespace:item_name",
  "emc": 123
}
```

- `id`: um item exato, com namespace confirmado na versão atual.
- `tag`: somente quando a mesma regra for correta para todos os itens cobertos.
- Não usar a chave `item`.
- Não duplicar IDs nem atribuir valor sem justificar a decisão.
- Não cadastrar um override apenas porque um item parece importante; confirmar primeiro o valor nativo do ProjectE.

## Fluxo obrigatório

1. Fazer backup externo do save e da instância.
2. Inspecionar o arquivo completo da tabela legada em ambiente local e registrar número de entradas, IDs duplicados, valores inválidos e hash do arquivo.
3. Guardar uma cópia imutável da tabela original antes de qualquer alteração.
4. Construir uma auditoria de grupos de itens por progressão: recursos básicos, minérios, processamento, máquinas, materiais avançados, itens de automação e itens de alto custo.
5. Conferir receitas, quantidades, subprodutos e ciclos que permitam gerar EMC infinito ou tornar progressão trivial.
6. Propor mudanças pequenas e revisáveis, sem reescrever milhares de entradas sem evidência.
7. Validar sintaxe JSON, IDs existentes, valores inteiros não negativos e duplicatas.
8. Testar em uma cópia da instância e do mundo; verificar início do jogo, carregamento dos mapeamentos, EMC de itens básicos, receitas representativas e Transmutation Table.
9. Anexar resultados e logs novos antes de abrir o PR de implementação.
10. Só integrar depois da revisão humana e da aprovação.

## Critérios de aceite

- A tabela original está preservada e recuperável.
- O diff contém somente alterações justificadas.
- Não há JSON inválido, IDs inventados nem valores negativos/fracionários.
- Não há falha de dependência nem erro de inicialização nos testes.
- EMC de itens básicos e uma amostra de itens de mods foram verificados no jogo.
- A Transmutation Table e as receitas representativas foram testadas.
- O save principal não foi usado como ambiente de diagnóstico.

## Estado atual

- [x] Branch de segurança criada a partir do snapshot de `main` antes da integração do plano.
- [x] Branch de trabalho alinhada à `main` atual para manter o futuro PR atualizado.
- [x] A tabela original de EMC continua intacta nesta branch.
- [ ] Inspecionar a tabela histórica completa sem a truncagem do conector.
- [ ] Definir a política de progressão e os alvos por categoria.
- [ ] Preparar e validar alterações seletivas.
- [ ] Testar em runtime.
- [ ] Abrir PR quando os dados e os testes sustentarem a proposta.

Este documento é uma política de trabalho, não a tabela de EMC final. Nenhum valor de item é alterado por esta política.
