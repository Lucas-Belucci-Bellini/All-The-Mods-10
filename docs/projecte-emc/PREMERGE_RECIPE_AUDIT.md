# Auditoria pré-merge: integridade das receitas

**Branch comparada:** `work/projecte-emc-balancing`  
**Base:** `main`  
**Escopo:** comparação estrutural dos arquivos Git versionados; não é uma execução do Minecraft.

## Resultado

**Nenhuma definição de receita foi adicionada, removida ou modificada pela branch em comparação com a main.** A comparação das árvores Git foi recursiva e não truncada.

- Arquivos versionados na main: 26.452
- Arquivos versionados na branch: 26.463
- Arquivos adicionados: 17
- Arquivos removidos: 6
- Arquivos modificados: 2
- Definições de receita identificáveis adicionadas/removidas/modificadas: 0
- JARs da pasta `mods/` alterados pela branch: 0

Os caminhos de dados de receitas, datapacks, definições em `kubejs/data/` e arquivos de receita existentes permanecem iguais à main. O diretório `kubejs/server_scripts/` muda apenas para adicionar o exportador de catálogo; os scripts de receitas que já existiam não foram alterados.

## O que mudou de fato

1. `README.md`: documentação de atualização segura com backup externo, nova instância e cópia do save.
2. `config/ProjectE/custom_emc.json`: a configuração ativa foi intencionalmente reduzida de uma tabela gerada de 67.531 entradas para `entries: []`.
3. A tabela antiga foi arquivada em `archive/custom_emc.legacy-generated.json`.
4. Os seis arquivos de configuração/estado do AutoEMC deixaram de estar no caminho ativo e foram preservados sob `docs/projecte-emc/archive/legacy-autoemc/`.
5. Foram adicionados documentos, política manual, ferramenta de exportação de overrides, testes e exportador KubeJS.

A remoção da configuração antiga afeta **valores EMC**, não as receitas nem o registro dos itens. É possível que itens antes cobertos apenas por overrides antigos fiquem sem EMC até a validação dos mapeadores nativos e a criação de exceções revisadas.

## Sobre o exportador JSON

O script está versionado e o fallback de ID foi ajustado para usar o método público `getId()` em vez de `getOrCreateId()`, que é oculto para scripts na versão KubeJS 2101 usada pelo modpack.

**O exportador ainda precisa ser executado no ATM10 real.** Esta auditoria não afirma que o arquivo gerado já existe, que contém todas as receitas dinâmicas de máquinas ou que não terá erros de serialização. Receitas implementadas exclusivamente em Java podem exigir análise adicional.

## Recomendação

- **Integridade estrutural das receitas:** aprovada — a branch não altera as definições de receita existentes.
- **Prontidão para merge de gameplay:** pendente — iniciar o modpack com a configuração EMC limpa, verificar pedra/pedregulho, terra, carvão, ferro e diamante, testar aprender/gastar/produzir na Transmutation Table e executar o exportador.
- **Save:** manter backup externo e não fazer merge/atualização na única instância de jogo sem seguir o procedimento do README.

Não mesclar automaticamente enquanto o teste de runtime estiver pendente.
