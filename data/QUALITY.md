# Calidad del corpus

Generado por `python data/build.py`. No editar a mano.

Filas candidatas: 4911. Aceptadas: 3362. Descartadas: 1549 (detalle fila por fila en `rejected.csv`).

## Composición final

| Split | Filas | Ataques | Legítimos | % ataque | Hard negatives (% de legítimos) |
|---|---|---|---|---|---|
| train | 1568 | 784 | 784 | 50% | 228 (29%) |
| val | 420 | 210 | 210 | 50% | 88 (42%) |
| test | 1374 | 687 | 687 | 50% | 288 (42%) |

### Por fuente

| Split | Fuente | Ataques | Legítimos | % del split |
|---|---|---|---|---|
| train | glaive_function_responses | 234 | 435 | 43% |
| train | injecagent | 81 | 28 | 7% |
| train | llmail_benign_emails | 0 | 57 | 4% |
| train | llmail_phase1 | 287 | 0 | 18% |
| train | synthetic_bank_statement | 40 | 51 | 6% |
| train | synthetic_chat_message | 37 | 52 | 6% |
| train | synthetic_email | 37 | 55 | 6% |
| train | synthetic_order_status | 35 | 52 | 6% |
| train | synthetic_wiki_doc | 33 | 54 | 6% |
| val | glaive_function_responses | 87 | 55 | 34% |
| val | injecagent | 48 | 15 | 15% |
| val | llmail_benign_emails | 0 | 30 | 7% |
| val | notinject | 0 | 16 | 4% |
| val | synthetic_calendar | 38 | 51 | 21% |
| val | synthetic_support_ticket | 37 | 43 | 19% |
| test | glaive_function_responses | 126 | 222 | 25% |
| test | injecagent | 66 | 24 | 7% |
| test | llmail_benign_emails | 0 | 95 | 7% |
| test | llmail_phase2 | 384 | 0 | 28% |
| test | notinject | 0 | 166 | 12% |
| test | synthetic_api_json | 39 | 60 | 7% |
| test | synthetic_product_review | 37 | 59 | 7% |
| test | synthetic_web_page | 35 | 61 | 7% |

### Categorías

| Categoría | train | val | test |
|---|---|---|---|
| exfiltration | 107 | 53 | 75 |
| fake_authority | 53 | 22 | 34 |
| hard_negative | 228 | 88 | 288 |
| human_adaptive | 287 | 0 | 384 |
| instruction_override | 69 | 26 | 37 |
| role_hijack | 61 | 23 | 36 |
| task_aligned | 30 | 12 | 18 |
| task_redirect | 68 | 27 | 36 |
| tool_misuse | 109 | 47 | 67 |
| tool_output | 556 | 122 | 399 |

## Descartes por criterio

| Motivo | glaive_function_responses | injecagent | llmail_benign_emails | llmail_phase1 | llmail_phase2 | notinject | synthetic_api_json | synthetic_bank_statement | synthetic_calendar | synthetic_chat_message | synthetic_email | synthetic_order_status | synthetic_product_review | synthetic_support_ticket | synthetic_web_page | synthetic_wiki_doc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| balance_attack_benign | 147 | 4 | 0 | 583 | 160 | 72 | 0 | 0 | 13 | 0 | 0 | 0 | 0 | 19 | 0 | 0 |
| balance_label_within_source | 0 | 177 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| exact_duplicate | 3 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | 1 | 0 | 1 |
| near_duplicate | 104 | 0 | 55 | 1 | 5 | 0 | 3 | 2 | 4 | 4 | 5 | 7 | 4 | 4 | 7 | 8 |
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
| train | 0.72 | 0.67 | 70% | 13% | 45% | 15% |
| val | 0.57 | 0.63 | 69% | 22% | 55% | 18% |
| test | 0.80 | 0.71 | 83% | 14% | 26% | 8% |

## Verificaciones de fuga

- Textos idénticos entre splits: **0**.
- Fuentes presentes en más de un split: glaive_function_responses, injecagent, llmail_benign_emails, notinject (separadas por tema, herramienta, caso de ataque o subconjunto; ver README).
- Filas con firmas de AgentDojo: **0**.
- Filas con datos de atacante de otro split: **0**.

## Longitud mediana (caracteres)

train: 234, val: 260, test: 251

