# data/splits

`dev.txt` / `test.txt`: conversation ids. `split_plan.json`: families and dosed drug-dose combinations per
split. `test.lock`: sha256 of every TEST file and gold label (check: `make split-lock`). The TEST split is
frozen (docs/hypothesis.md); the generator refuses to change it without `--refreeze` + a decision entry.
