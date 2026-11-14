# Calidad del corpus

Generado por `python data/build.py`. No editar a mano.

Filas candidatas: 5259. Aceptadas: 3878. Descartadas: 1561 (detalle fila por fila en `rejected.csv`).

## Composición final

| Split | Filas | Ataques | Legítimos | % ataque | Hard negatives (% de legítimos) |
|---|---|---|---|---|---|
| train | 1784 | 892 | 892 | 50% | 336 (38%) |
| val | 532 | 266 | 266 | 50% | 166 (62%) |
| test | 1562 | 781 | 781 | 50% | 382 (49%) |

### Por fuente

| Split | Fuente | Ataques | Legítimos | % del split |
|---|---|---|---|---|
| train | glaive_function_responses | 253 | 435 | 39% |
| train | injecagent | 84 | 28 | 6% |
| train | llmail_benign_emails | 0 | 57 | 3% |
| train | llmail_phase1 | 317 | 0 | 18% |
| train | synthetic_bank_statement | 40 | 51 | 5% |
| train | synthetic_banking | 26 | 78 | 6% |
| train | synthetic_chat_message | 37 | 52 | 5% |
| train | synthetic_email | 37 | 55 | 5% |
| train | synthetic_key_injection | 30 | 30 | 3% |
| train | synthetic_order_status | 35 | 52 | 5% |
| train | synthetic_wiki_doc | 33 | 54 | 5% |
| val | glaive_function_responses | 87 | 44 | 25% |
| val | injecagent | 48 | 9 | 11% |
| val | llmail_benign_emails | 0 | 30 | 6% |
| val | notinject | 0 | 10 | 2% |
| val | synthetic_banking | 26 | 61 | 16% |
| val | synthetic_calendar | 38 | 43 | 15% |
| val | synthetic_key_injection | 30 | 25 | 10% |
| val | synthetic_support_ticket | 37 | 44 | 15% |
| test | glaive_function_responses | 124 | 222 | 22% |
| test | injecagent | 66 | 24 | 6% |
| test | llmail_benign_emails | 0 | 95 | 6% |
| test | llmail_phase2 | 421 | 0 | 27% |
| test | notinject | 0 | 166 | 11% |
| test | synthetic_api_json | 40 | 60 | 6% |
| test | synthetic_banking | 25 | 64 | 6% |
| test | synthetic_key_injection | 30 | 30 | 4% |
| test | synthetic_product_review | 38 | 59 | 6% |
| test | synthetic_web_page | 37 | 61 | 6% |

### Categorías

| Categoría | train | val | test |
|---|---|---|---|
| exfiltration | 123 | 58 | 80 |
| fake_authority | 54 | 22 | 36 |
| hard_negative | 336 | 166 | 382 |
| human_adaptive | 317 | 0 | 421 |
| instruction_override | 66 | 26 | 37 |
| key_injection | 30 | 30 | 30 |
| role_hijack | 69 | 23 | 40 |
| task_aligned | 51 | 33 | 38 |
| task_redirect | 71 | 27 | 34 |
| tool_misuse | 111 | 47 | 65 |
| tool_output | 556 | 100 | 399 |

### Formato YAML (como AgentDojo)

35% de las salidas estructuradas de glaive_function_responses, injecagent, synthetic_key_injection, synthetic_api_json, synthetic_banking van en YAML (`yaml.safe_dump`, igual que AgentDojo).

| Split | Ataques en YAML | Legítimos en YAML | `key_injection` en YAML |
|---|---|---|---|
| train | 160 | 190 | 8 |
| val | 63 | 27 | 13 |
| test | 91 | 132 | 8 |

## Descartes por criterio

| Motivo | glaive_function_responses | injecagent | llmail_benign_emails | llmail_phase1 | llmail_phase2 | notinject | synthetic_api_json | synthetic_bank_statement | synthetic_banking | synthetic_calendar | synthetic_chat_message | synthetic_email | synthetic_key_injection | synthetic_order_status | synthetic_product_review | synthetic_support_ticket | synthetic_web_page | synthetic_wiki_doc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| balance_attack_benign | 141 | 7 | 0 | 553 | 123 | 78 | 0 | 0 | 13 | 21 | 0 | 0 | 5 | 0 | 0 | 18 | 0 | 0 |
| balance_label_within_source | 0 | 177 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| exact_duplicate | 3 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 1 | 1 | 1 |
| near_duplicate | 104 | 0 | 55 | 1 | 5 | 0 | 2 | 2 | 49 | 4 | 4 | 5 | 0 | 7 | 3 | 4 | 4 | 8 |
| not_english | 22 | 0 | 0 | 29 | 9 | 31 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| not_english+pii_like | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| pii_like | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| too_short | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| too_short+not_english | 0 | 0 | 0 | 0 | 0 | 54 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Atajos medidos (0,5 = la señal no ayuda a separar)

Un detector podría aprender estas señales en vez de la intención. Se miden para vigilarlas.

La AUC *dentro de fuente* (promedio ponderado entre fuentes con ambas etiquetas) es la que importa para el entrenamiento; la del split completo mezcla estilos de fuentes distintas.

| Split | AUC longitud (split) | AUC longitud (dentro de fuente) | Ataques con URL/correo | Legítimos con URL/correo | Ataques con 'assistant'/'AI' | Legítimos con 'assistant'/'AI' |
|---|---|---|---|---|---|---|
| train | 0.74 | 0.70 | 69% | 13% | 46% | 13% |
| val | 0.60 | 0.64 | 62% | 21% | 50% | 15% |
| test | 0.82 | 0.73 | 81% | 13% | 25% | 7% |

## Verificaciones de fuga

- Textos idénticos entre splits: **0**.
- Fuentes presentes en más de un split: glaive_function_responses, injecagent, llmail_benign_emails, notinject, synthetic_banking, synthetic_key_injection (separadas por tema, herramienta, caso de ataque o subconjunto; ver README).
- Filas con firmas de AgentDojo: **0**.
- Filas con datos de atacante de otro split: **0**.

## Longitud mediana (caracteres)

train: 226, val: 238, test: 240


## Manifiestos MCP (`mcp_manifests.jsonl`, solo evaluación)

Para `check(texto, origen="manifiesto")`. Se genera en local (MCPTox no declara licencia y trae payloads funcionales: no se sube).

| Split | Fuente | Envenenadas | Limpias | Hard negatives | Largo mediano |
|---|---|---|---|---|---|
| val | mcptox_poisoned | 230 | 0 | 0 | 242 |
| val | mcptox_clean | 0 | 143 | 23 | 119 |
| val | toolace_manifests | 0 | 86 | 5 | 238 |
| test | mcptox_poisoned | 254 | 0 | 0 | 233 |
| test | mcptox_clean | 0 | 158 | 10 | 49 |
| test | toolace_manifests | 0 | 85 | 3 | 213 |

AUC de la longitud (0,5 = no ayuda): envenenadas vs todas las limpias **0.66**; envenenadas vs solo limpias de MCPTox **0.72**. Reportar los falsos positivos por fuente: los de `mcptox_clean` son el caso real, los de `toolace_manifests` controlan el atajo de longitud.

Descartes: mcptox_clean / not_english: 13, mcptox_clean / not_english+too_short: 30, mcptox_clean / too_long: 1, mcptox_clean / too_short: 17, mcptox_poisoned / pii_like: 1, toolace_manifests / not_english: 1.

Riesgos en las envenenadas: information_manipulation (108), privacy_leakage (97), service_disruption (72), data_tampering (45), infrastructure_damage (41), credential_leakage (40), code_injection (22), financial_loss (21), instruction_tampering (21), message_hijacking (15), other (2).
