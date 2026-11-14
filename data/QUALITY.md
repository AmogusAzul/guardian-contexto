# Calidad del corpus

Generado por `python data/build.py`. No editar a mano.

Filas candidatas: 4911. Aceptadas: 3542. Descartadas: 1549 (detalle fila por fila en `rejected.csv`).

## Composición final

| Split | Filas | Ataques | Legítimos | % ataque | Hard negatives (% de legítimos) |
|---|---|---|---|---|---|
| train | 1628 | 814 | 814 | 50% | 258 (32%) |
| val | 480 | 240 | 240 | 50% | 124 (52%) |
| test | 1434 | 717 | 717 | 50% | 318 (44%) |

### Por fuente

| Split | Fuente | Ataques | Legítimos | % del split |
|---|---|---|---|---|
| train | glaive_function_responses | 228 | 435 | 41% |
| train | injecagent | 82 | 28 | 7% |
| train | llmail_benign_emails | 0 | 57 | 4% |
| train | llmail_phase1 | 292 | 0 | 18% |
| train | synthetic_bank_statement | 40 | 51 | 6% |
| train | synthetic_chat_message | 37 | 52 | 5% |
| train | synthetic_email | 37 | 55 | 6% |
| train | synthetic_key_injection | 30 | 30 | 4% |
| train | synthetic_order_status | 35 | 52 | 5% |
| train | synthetic_wiki_doc | 33 | 54 | 5% |
| val | glaive_function_responses | 87 | 52 | 29% |
| val | injecagent | 48 | 13 | 13% |
| val | llmail_benign_emails | 0 | 30 | 6% |
| val | notinject | 0 | 16 | 3% |
| val | synthetic_calendar | 38 | 50 | 18% |
| val | synthetic_key_injection | 30 | 30 | 12% |
| val | synthetic_support_ticket | 37 | 49 | 18% |
| test | glaive_function_responses | 120 | 222 | 24% |
| test | injecagent | 66 | 24 | 6% |
| test | llmail_benign_emails | 0 | 95 | 7% |
| test | llmail_phase2 | 386 | 0 | 27% |
| test | notinject | 0 | 166 | 12% |
| test | synthetic_api_json | 40 | 60 | 7% |
| test | synthetic_key_injection | 30 | 30 | 4% |
| test | synthetic_product_review | 38 | 59 | 7% |
| test | synthetic_web_page | 37 | 61 | 7% |

### Categorías

| Categoría | train | val | test |
|---|---|---|---|
| exfiltration | 107 | 53 | 75 |
| fake_authority | 53 | 22 | 36 |
| hard_negative | 258 | 124 | 318 |
| human_adaptive | 292 | 0 | 386 |
| instruction_override | 66 | 26 | 35 |
| key_injection | 30 | 30 | 30 |
| role_hijack | 59 | 23 | 36 |
| task_aligned | 30 | 12 | 18 |
| task_redirect | 68 | 27 | 35 |
| tool_misuse | 109 | 47 | 66 |
| tool_output | 556 | 116 | 399 |

## Descartes por criterio

| Motivo | glaive_function_responses | injecagent | llmail_benign_emails | llmail_phase1 | llmail_phase2 | notinject | synthetic_api_json | synthetic_bank_statement | synthetic_calendar | synthetic_chat_message | synthetic_email | synthetic_order_status | synthetic_product_review | synthetic_support_ticket | synthetic_web_page | synthetic_wiki_doc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| balance_attack_benign | 162 | 5 | 0 | 578 | 158 | 72 | 0 | 0 | 14 | 0 | 0 | 0 | 0 | 13 | 0 | 0 |
| balance_label_within_source | 0 | 177 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| exact_duplicate | 3 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | 1 | 1 | 1 |
| near_duplicate | 104 | 0 | 55 | 1 | 5 | 0 | 2 | 2 | 4 | 4 | 5 | 7 | 3 | 4 | 4 | 8 |
| not_english | 22 | 0 | 0 | 29 | 9 | 31 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| not_english+pii_like | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| pii_like | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| too_short | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| too_short+not_english | 0 | 0 | 0 | 0 | 0 | 54 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Atajos medidos (0,5 = la señal no ayuda a separar)

Un detector podría aprender estas señales en vez de la intención. Se miden para vigilarlas.

La AUC *dentro de fuente* (promedio ponderado entre fuentes con ambas etiquetas) es la que importa para el entrenamiento; la del split completo mezcla estilos de fuentes distintas.

| Split | AUC longitud (split) | AUC longitud (dentro de fuente) | Ataques con URL/correo | Legítimos con URL/correo | Ataques con 'assistant'/'AI' | Legítimos con 'assistant'/'AI' |
|---|---|---|---|---|---|---|
| train | 0.72 | 0.67 | 71% | 14% | 44% | 14% |
| val | 0.57 | 0.62 | 68% | 25% | 51% | 17% |
| test | 0.80 | 0.70 | 84% | 15% | 25% | 8% |

## Verificaciones de fuga

- Textos idénticos entre splits: **0**.
- Fuentes presentes en más de un split: glaive_function_responses, injecagent, llmail_benign_emails, notinject, synthetic_key_injection (separadas por tema, herramienta, caso de ataque o subconjunto; ver README).
- Filas con firmas de AgentDojo: **0**.
- Filas con datos de atacante de otro split: **0**.

## Longitud mediana (caracteres)

train: 232, val: 252, test: 246


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
