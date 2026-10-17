# ProjectE Integration — auditoria de dependências

**Repositório:** `Lucas-Belucci-Bellini/All-The-Mods-10`  
**Branch:** `work/projecte-emc-balancing`  
**Minecraft:** 1.21.1 / NeoForge 21.1.259  
**Versões no modlist:** ProjectE 1.1.0, ProjectE Integration 8.4.0, Project Expansion 1.0.6, AutoEMC 2.1.1.

## Resposta resumida

Até aqui, **não encontrei evidência de que os mods de conteúdo do ATM10 precisem do ProjectE Integration para funcionar**. Ele é um addon de integração do ProjectE: sua função publicada é adicionar mapeadores/conversões de receitas de outros mods, não fornecer os próprios mods suportados.

Entretanto, não é seguro declarar que pode ser removido mantendo todos os addons sem uma ressalva: a página pública do AutoEMC menciona ProjectE Integration nos requisitos, mas a descrição mistura versões e a seção de requisitos exibida especifica Minecraft 1.16.5/Forge. Não encontrei no código-fonte publicado uma declaração de dependência que corresponda inequivocamente ao arquivo AutoEMC 2.1.1 para Minecraft 1.21.1 que está nesta instância.

## Evidência verificada

1. `logs/modlist.txt` registra 543 mods e uma entrada `projecteintegration` (ProjectE-Integration 8.4.0), além de `projecte`, `projectexpansion` e `autoemc`. O modlist demonstra que estão instalados, mas não contém a lista das dependências declaradas pelos JARs.
2. O `manifest.json` do pacote base ATM10 v8.3 contém ProjectE (CurseForge project ID 238222, `required: true`) e não contém ProjectE Integration (ID 313402) nem AutoEMC (ID 1595011). Isso mostra que o pacote ATM10 original não os declara como arquivos do pack. Como a instância é modificada, o manifesto base sozinho não prova as dependências dos addons adicionados.
3. A [página oficial de ProjectE Integration no CurseForge](https://www.curseforge.com/minecraft/mc-mods/projecte-integration) descreve o mod como suporte/conversões para receitas de outros mods. A página de relações lista os mods suportados como dependências **opcionais** do ProjectE Integration, o que significa que os mods suportados não precisam dele apenas para existir.
4. A [página AutoEMC no Modrinth](https://modrinth.com/project/autoemc) menciona ProjectE Integration na seção Requirements. Porém, a documentação publica vários alvos de Minecraft e o texto de requisitos começa com 1.16.5/Forge; por isso, não a trato como prova conclusiva da dependência obrigatória do JAR 2.1.1 para 1.21.1.
5. Em `config/autoemc-common.toml`, a configuração da instância usa `useBundledProjectEMappingConversions = true` e `useProjectEIntegrationBaselines = true`; os comentários indicam que parte das conversões e dos valores-base está incorporada no próprio AutoEMC. Isso sugere que ele possui dados embutidos, mas não prova a ausência de uma dependência declarada no metadata do JAR.

## Conclusão operacional

- **Mods de conteúdo do ATM10:** não há evidência encontrada de dependência obrigatória do ProjectE Integration.
- **ProjectE:** a função descrita do Integration é adicionar conversões; a instalação base do ATM10 declara ProjectE, não ProjectE Integration.
- **AutoEMC 2.1.1:** ponto ainda não fechado apenas por documentação pública; confirmar em execução/metadados desta versão antes de afirmar que é independente.
- **Não remover definitivamente ainda.** Fazer o teste em uma cópia da instância.

## Procedimento seguro para confirmar

1. Duplicar a instância e o mundo; nunca usar o save principal para diagnóstico inicial.
2. Na cópia, desativar temporariamente ProjectE Integration e AutoEMC juntos, mantendo ProjectE e Project Expansion. Isso evita que um possível requisito declarado pelo AutoEMC impeça o teste.
3. Abrir o jogo e um mundo de teste; verificar EMC de pedra, terra e diamante e se os itens podem ser aprendidos na Transmutation Table.
4. Conferir `latest.log` para dependências ausentes e erros do ProjectE.
5. Se EMC voltar, a presença de ProjectE Integration está envolvida no problema. Depois, testar AutoEMC 2.1.1 sozinho (sem ProjectE Integration) em outra cópia, observando se o NeoForge declara uma dependência faltante e se a geração de EMC funciona.
6. Se remover ambos não restaurar EMC, investigar o erro original do ProjectE e testar separadamente a hipótese de incompatibilidade com Immersive Engineering.

**Não testado nesta auditoria:** iniciar o jogo a partir desta conversa. A conclusão é baseada no manifest, modlist, configuração e documentação pública; o teste de runtime continua sendo necessário.
