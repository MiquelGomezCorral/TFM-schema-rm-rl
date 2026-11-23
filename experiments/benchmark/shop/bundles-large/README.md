# Large shop bundle files, compressed

The repository takes no new file over 1 MB (the `check-added-large-files` hook). 31 files of the frozen FARM shop
bundles are bigger: in `shop-boil`, `shop-boil~p1` to `~p3` and `shop-quiet-first~p1` to `~p3`. They are kept here
gzipped, at the same path they have under `../bundles/`.

Put them back before training or checking those bundles, from the repository root, on any clone (the cluster's too):

```bash
find experiments/benchmark/shop/bundles-large -name '*.gz' | while read -r f; do
  out=experiments/benchmark/shop/bundles/${f#experiments/benchmark/shop/bundles-large/}
  gunzip -c "$f" > "${out%.gz}"
done
```

The copies were made with `gzip -9 -n` and restore byte for byte (checked on all 31, 2026-11-23).
