# Leitura Imagem ROM

Laboratorio para investigar dados internos do jogo de PS1 `Yu-Gi-Oh! Remastered Perfected (Drop x15)`.

## Caminho da imagem

```text
C:\Users\fimal\Downloads\Yu-Gi-Oh! Remastered Perfected (Drop x15)\Yu-Gi-Oh! Remastered Perfected (Drop x15).bin
```

## Primeiro fluxo

1. Listar os arquivos dentro da imagem:

```powershell
& "C:\Users\fimal\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" tools\psx_iso.py "C:\Users\fimal\Downloads\Yu-Gi-Oh! Remastered Perfected (Drop x15)\Yu-Gi-Oh! Remastered Perfected (Drop x15).bin" list
```

2. Extrair os arquivos para a pasta `extracted`:

```powershell
& "C:\Users\fimal\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" tools\psx_iso.py "C:\Users\fimal\Downloads\Yu-Gi-Oh! Remastered Perfected (Drop x15)\Yu-Gi-Oh! Remastered Perfected (Drop x15).bin" extract extracted
```

Para substituir um arquivo por outro de tamanho idêntico, inclusive dentro
de imagens RAW Mode 2/Form 1 com recálculo de EDC/ECC:

```powershell
& "C:\Users\fimal\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" tools\psx_iso.py "imagem.iso" replace "DATA/WA_MRG.MRG" "WA_MRG.MRG"
```

## Aplicativo de quantidade de drops

O aplicativo Windows pronto para uso esta em
`dist/YGO_FM_Drop_Editor.exe`. Ele reconhece `WA_MRG.MRG`, imagens `.iso`,
imagens `.bin` e `.cue` de uma unica faixa de dados. A interface oferece
Drop x1, x5 e x15, salvamento como copia e substituicao do original com
backup automatico.

O codigo-fonte da interface esta em `tools/drop_count_app.py`. O aplicativo
reutiliza a validacao dos 22 bytes de `tools/edit_drop_count.py` e a
substituicao transacional com EDC/ECC de `tools/psx_iso.py`.

3. Procurar tabelas candidatas:

- arquivos grandes com extensoes como `.BIN`, `.DAT`, `.PAC`;
- textos com nomes de cartas;
- blocos binarios com registros de tamanho fixo;
- tabelas de IDs que referenciem duas cartas de entrada e uma carta de saida.

## Achados iniciais

A imagem foi reconhecida como BIN raw de PS1:

- setor fisico: `2352` bytes;
- offset de dados: `24` bytes;
- volume ISO9660 valido com `SYSTEM.CNF` e `SLUS_014.11`.

Arquivos extraidos:

```text
SYSTEM.CNF
SLUS_014.11
DATA/SU.MRG
DATA/SD_SE.DAT
DATA/SD_BGM.DAT
DATA/WA_MRG.MRG
DATA/MASTER.XA
DATA/MODEL.MRG
DATA/MOVIE.STR
```

Triagem:

- `SLUS_014.11`: executavel PS1; contem strings de debug e referencias a `SU.MRG`.
- `SU.MRG`: contem strings de creditos, incluindo `Card_Rule_Co-Design`, mas esse trecho e credito, nao tabela de fusao.
- `WA_MRG.MRG`: parece pacote grande de dados visuais/arte.
- `SD_*`, `MASTER.XA`, `MOVIE.STR`: audio/video, baixa prioridade para fusoes.

## Hipoteses iniciais encerradas

- A tabela de fusoes nao esta em `SU.MRG` nem na permutacao encontrada no executavel. Ela foi confirmada em `WA_MRG.MRG`.
- Os IDs e nomes do mod foram extraidos diretamente de `SLUS_014.11`; nao e necessario assumir a numeracao do jogo original.
- A rotina foi validada com uma fusao conhecida e pela emulacao exaustiva do algoritmo documentado.

## Achados da primeira rodada de pesquisa

Notas detalhadas em `references/research-notes.md`.

- Fontes publicas importantes:
  - GameFAQs tem um indice de guias para o jogo, incluindo Fusion FAQ, Fusion Guide e Card Password/Starchip Guide.
  - O Fusion Guide de 2020 afirma cobrir `50242` fusoes e cita bancos `FmDatabase.db` e `FmDatabaseWithGS.db` com dados de cartas, fusoes e drops.
  - O Card Password/Starchip Guide confirma IDs e stats publicos, por exemplo `001` Blue Eyes White Dragon, `016` Time Wizard e `069` Thousand Dragon.
- Achado local forte:
  - `SLUS_014.11` tem uma tabela `uint16le` no offset `0x001C558C`.
  - Essa tabela contem `723` valores e e uma permutacao perfeita de `0..722`.
  - A investigacao posterior confirmou que ela nao e a tabela de fusoes. Seu papel exato continua desconhecido, mas nao bloqueia mais a extracao.
- Achado negativo util:
  - ATK/DEF conhecidos nao aparecem como pares `uint16le` simples em `SLUS_014.11` nem em `DATA/SU.MRG`.
  - Isso sugere stats codificados, compactados, em outra ordem, ou guardados em outra estrutura.

Ferramentas adicionadas:

- `tools/find_candidate_tables.py`: procura regioes com registros numericos parecidos com IDs de cartas.
- `tools/find_u16_permutations.py`: encontra tabelas que sao permutacoes `uint16`.
- `tools/find_mips_address_refs.py`: procura referencias MIPS simples para enderecos de RAM.
- `tools/find_known_card_stats.py`: procura padroes de ATK/DEF conhecidos.
- `tools/export_u16_table_csv.py`: exporta tabelas `uint16le` para CSVs de inspecao manual.

## CSVs antigos da hipotese de permutacao

Estes CSVs foram mantidos como registro da investigacao, mas nao representam fusoes. A tabela `uint16le` encontrada em `SLUS_014.11` no offset `0x001C558C` foi exportada em tres visoes:

- `exports/slus_01411_0x001C558C_card_id_permutation_by_position.csv`: ordem original da tabela.
- `exports/slus_01411_0x001C558C_card_id_permutation_by_card_id.csv`: de/para por ID, melhor para preencher nomes e tipos conhecidos.
- `exports/slus_01411_0x001C558C_card_id_permutation_groups_of_3.csv`: agrupamento em trios, util para procurar padroes visuais.

Tambem existem copias com separador `;` em `exports/pt_br_semicolon/`, que costumam abrir melhor em planilhas configuradas para pt-BR.

Comando usado:

```powershell
& "C:\Users\fimal\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" tools\export_u16_table_csv.py extracted\SLUS_014.11 --offset 0x001C558C --count 723 --group-size 3 --output-dir exports --prefix slus_01411_0x001C558C_card_id_permutation
```

## Extracao confirmada das fusoes

A tabela real de fusoes foi localizada em `DATA/WA_MRG.MRG`, no offset `0x00B87800`. Ela usa um indice de offsets por carta e blocos compactados de cinco bytes para guardar duas fusoes.

O mod reorganiza os IDs das cartas, entao listas de IDs do jogo original nao servem como de/para direto. Os nomes e atributos usados nos CSVs sao lidos do proprio `SLUS_014.11` do mod.

Executar:

```powershell
& "C:\Users\fimal\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" tools\extract_fusions.py extracted\DATA\WA_MRG.MRG extracted\SLUS_014.11 --output-dir exports\fusions
```

Saidas com separador `;` e codificacao compativel com Excel:

- `exports/fusions/cards.csv`: 722 IDs, nomes, ATK, DEF, estrelas guardias, tipo, nivel e atributo.
- `exports/fusions/fusions_effective.csv`: 9.020 combinacoes que a rotina do jogo realmente retorna.
- `exports/fusions/fusions_declared_raw.csv`: 9.174 registros brutos, com offsets e diagnostico de entradas efetivas, sombreadas ou inalcancaveis.
- `exports/fusions/summary.json`: resumo reproduzivel da extracao.

Validacao conhecida no mod:

```text
ID 1 Baby Dragon + ID 12 Time Wizard = ID 219 Thousand Dragon
```

Detalhes tecnicos e fontes estao em `references/research-notes.md`.

## Drops dos oponentes

O extrator le diretamente do mod os tres pools de recompensa dos 39 duelistas:

```powershell
& "C:\Users\fimal\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" tools\extract_drops.py extracted\DATA\WA_MRG.MRG extracted\SLUS_014.11 --output-dir exports\drops
```

Resultados:

- `drop_rates.csv`: somente cartas com chance maior que zero, com peso `x/2048`, percentual e chance media `1 em N`.
- `drop_rates_all_cards.csv`: auditoria completa dos 39 duelistas, tres pools e 722 cartas, incluindo pesos zero.
- `drop_pools_summary.csv`: quantidade de cartas possiveis e offset de cada pool.
- `drop_rates.json`: estrutura hierarquica por duelista e pool.
- `guia_drops_pt_br.md`: explicacao dos ranks e resumo dos pools.
- `summary.json`: totais e caminhos gerados.

Os pools sao `S/A POW`, `B/C/D POW/TEC` e `S/A TEC`. O extrator exige que cada um some exatamente 2.048 antes de gerar os arquivos.

## Cartas usadas pelos oponentes

Cada duelista possui um unico pool ponderado usado para montar seu deck de 40 cartas:

```powershell
& "C:\Users\fimal\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" tools\extract_opponent_decks.py extracted\DATA\WA_MRG.MRG extracted\SLUS_014.11 --output-dir exports\opponent_decks
```

Resultados:

- `opponent_deck_rates.csv`: cartas que o oponente pode usar, com peso `x/2048`, percentual e chance media `1 em N` por tentativa de selecao.
- `opponent_deck_rates_all_cards.csv`: auditoria completa incluindo pesos zero.
- `opponent_decks_summary.csv`: tamanho do pool, maior peso e offset de cada oponente.
- `opponent_deck_rates.json`: estrutura hierarquica por oponente.
- `guia_decks_oponentes_pt_br.md`: explicacao e resumo dos 39 decks.

O peso e usado na geracao do deck. Depois, as 40 cartas geradas sao embaralhadas, portanto ele nao representa diretamente a chance de comprar a carta em um turno especifico.

## Regras memorizaveis e tipos das cartas

O analisador de padroes transforma as 9.020 fusoes efetivas em produtos exatos de conjuntos:

```text
Conjunto A x Conjunto B = carta resultante
```

Aqui `Dragon`, `Spellcaster`, `Fiend`, `Rock` etc. sao chamados de `primary_type`. Esse e o campo que o usuario normalmente chama de atributo ao falar das familias de monstros; ele nao e o atributo elemental moderno do TCG.

Executar:

```powershell
& "C:\Users\fimal\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" tools\analyze_fusion_patterns.py exports\fusions\cards.csv exports\fusions\fusions_effective.csv --output-dir exports\fusion_patterns
```

Resultados:

- `cards_gameplay.csv`: ID, nome, primary type, ATK e DEF das 722 cartas.
- `fusion_rules_core.csv`: 79 regras grandes que cobrem 6.300 fusoes (69,8%).
- `fusion_rules_memorizable.csv`: 246 regras com pelo menos cinco combinacoes que cobrem 8.444 fusoes (93,6%).
- `fusion_rules.csv`: todas as 627 regras, incluindo grupos pequenos e fusoes exatas.
- `material_groups.csv`: definicao resumida dos 392 conjuntos encontrados.
- `material_group_members.csv`: uma linha por carta pertencente a cada conjunto.
- `fusion_attack_exceptions.csv`: 22 violacoes da regra de ATK e nove resultados com ATK zero.
- `memorization_guide.md`: guia textual com os grupos mais reutilizados e as regras core.
- `guia_memorizacao_pt_br.md`: versao completa em portugues, mantendo os primary types em ingles e classificando todas as cartas por papel na cadeia.
- `card_fusion_roles.csv`: classificacao filtravel das 722 cartas, contagens de uso e uma rota curta representativa para cada intermediaria.
- `distribuicao_tamanho_grupos.csv`: quantidade de grupos por numero de cartas no conjunto.
- `distribuicao_tamanho_regras.csv`: quantidade de regras por numero de combinacoes cobertas.
- `distribuicao_tamanhos.md`: leitura resumida das duas distribuicoes em portugues.

Validacao matematica:

- expandir os 627 produtos de conjuntos reconstrui exatamente as 9.020 fusoes;
- nenhuma fusao e inventada, omitida ou coberta duas vezes;
- entre as 9.011 fusoes cujo resultado tem ATK maior que zero, 8.989 (99,76%) possuem ambos os materiais com ATK estritamente menor que o resultado;
- as 22 excecoes restantes ficam identificadas individualmente.

Classificacao das cartas na cadeia de fusoes:

- 204 materiais iniciais: servem como material, mas nunca sao resultado;
- 142 intermediarias de nivel 1: precisam de mais uma fusao na menor rota ate uma final;
- 18 intermediarias de nivel 2;
- uma intermediaria de nivel 3 (`Bracchio-raidus`);
- 76 fusoes finais: sao resultado e nao servem como material;
- 281 cartas sem participacao na tabela efetiva.

O nivel de uma intermediaria e a menor quantidade de fusoes adicionais necessaria para chegar a uma fusao final. Uma carta pode ter rotas alternativas mais longas; o CSV e o guia mostram uma rota curta representativa.

## Protocolo de pesquisa externa

Este projeto usa a skill local `.codex/skills/rom-internet-research` como agente de pesquisa.

Sempre que a investigacao chegar numa duvida relevante, consulte essa skill antes de seguir por tentativa e erro longa. Exemplos:

- onde ficam as fusoes;
- como `SU.MRG` ou outro container funciona;
- como mapear IDs numericos de cartas para nomes;
- se `SLUS_014.11` contem tabelas conhecidas;
- se algum mod, ferramenta, disassembly ou post publico ja resolveu a mesma parte.

Fluxo esperado:

1. O processo principal formula uma pergunta estreita, com arquivos, offsets e achados locais.
2. Um sub-agente de pesquisa, quando disponivel, usa a skill `rom-internet-research` para procurar fontes na internet.
3. O retorno deve separar fatos verificados, inferencias e proximos experimentos locais.
4. Achados com fonte podem atualizar este README, notas do projeto ou scripts em `tools/`.
5. Nada encontrado na internet deve substituir a analise local sem uma checagem reproduzivel no binario extraido.

## Imagens das cartas em WA_MRG.MRG

As 722 cartas ficam em registros fixos dentro de `DATA/WA_MRG.MRG`:

- inicio da regiao: `0x169000` (`1.478.656`);
- tamanho de cada registro: `0x3800` (`14.336` bytes);
- indice do registro: `card_id - 1`.

Layout de cada registro:

- `+0x0000`: arte principal, 102x96, 8 bpp, 9.792 bytes;
- `+0x2640`: paleta principal, 256 cores ABGR1555 little-endian, 512 bytes;
- `+0x2840`: nome, 96x14, 4 bpp, 672 bytes;
- `+0x2AE0`: miniatura, 40x32, 8 bpp, 1.280 bytes;
- `+0x2FE0`: paleta da miniatura, 256 cores ABGR1555, 512 bytes.

Extrair arte, nome e miniatura de IDs especificos:

```powershell
& "C:\Users\fimal\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" tools\extract_card_images.py extracted\DATA\WA_MRG.MRG exports\card_images --card-id 1 --card-id 199 --kind all
```

Para exportar as 722 artes principais, use `--all-cards --kind full`.

O mesmo layout foi validado nos arquivos Remastered, Naruto e Naruto Shippuden Final.

## Meta

Chegar numa tabela exportavel, de preferencia `CSV`/`JSON`, com:

- carta A;
- carta B;
- resultado da fusao;
- condicoes especiais, se existirem.

## Catálogo com múltiplos mods

O catálogo local em `catalogo/index.html` reúne dois datasets selecionáveis:

- `Remastered Perfected`, extraído em `exports/`;
- `Naruto Drop x15`, extraído em `exports/naruto/`.

O dataset Naruto usa `extracted_naruto/SLUS_025.11` e
`extracted_naruto/DATA/WA_MRG.MRG`. Ele contém cartas, fusões, três pools de
drop por oponente, decks probabilísticos e compatibilidades de equipamento.

## Retratos dos oponentes

Os retratos compactos da seleção de oponentes também ficam em
`DATA/WA_MRG.MRG`, a partir de `0x00F55000`. São 40 registros de `0x980` bytes:
imagem indexada de `48 x 48` e paleta PS1 de 64 cores.

```powershell
& "C:\Users\fimal\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" tools\extract_opponent_images.py extracted\DATA\WA_MRG.MRG exports\opponent_images\mapped\remastered --opponents --first-slot 2
```

Nos três jogos, o slot 1 é o ícone que abre o deck no menu Free Duel; ele não é
um oponente. Por isso, os IDs 1-39 usam os slots 2-40 e o padrão seguro é
`--first-slot 2`. Use `--deck-icon-output` para preservar o primeiro slot com o
nome `free_duel_deck.png`, sem incluí-lo no HTML. A investigação completa está
em `references/opponent-images-investigation.md`.

Para regenerar o payload consumido pelo HTML após uma extração:

```powershell
& "C:\Users\fimal\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" tools\build_catalog_data.py
```
