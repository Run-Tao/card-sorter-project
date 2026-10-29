# OOD gate evaluation

Template similarity threshold: 0.55

| split | n | min | median | p90 | max | OOD rate |
|---|---|---|---|---|---|---|
| jackfurby_test | 260 | 0.371 | 0.958 | 0.988 | 1.0 | 1.5% |
| real52_test | 104 | 0.165 | 0.428 | 0.543 | 0.655 | 90.4% |

Synthetic = same design as training; real = another deck design.
A high synthetic OOD rate would mean false rejection; a high real OOD rate
is expected and is the reason unknown designs are sent to review/enrollment.
