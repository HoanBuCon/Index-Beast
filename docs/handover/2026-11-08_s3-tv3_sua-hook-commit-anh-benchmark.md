# TV3 ? S?a l?i hook khi commit ?nh benchmark

Ng?y08/11/2026 (Asia/Saigon) ? MinhMuc ? nh?nh `feature/s3-tv3-evidence-media-build`.
Ch? s?a local v? chu?n b? staging; kh?ng commit/push/merge.

## Nguy?n nh?n th?c t?

??c Git extension log VS Code, l?n commit01:20:54 ng?y08/11 th?t b?i t?i
`check-added-large-files`, kh?ng ph?i `trailing-whitespace` (Passed).
Repository gi?i h?n file m?i1.024KB, hai ?nh benchmark PNG v??t ng??ng:

- `2a2818903712b9eeaa8b32ad94fe7e0a343502834759e84c7b7cf4dd7c5d48f2.png`:1.452KB.
- `8c3c1c82bbb5774d3f0b585cb5a72275a121392e55959ddc8b25544c873686a3.png`:1.350KB.

C?c ?nh ??u thu?c `docs/testing/2026-11-07_evidence-media-build-10/images/`, l? output
benchmark l?u ?? m? ki?m tra; ch?a t?n t?i trong HEAD, ?ang ???c th?m m?i v?o index.

## S?a

- `.gitignore`: th?m ??ng th? m?c ?nh c?a run n?y, kh?ng ignore code/report ho?c to?n b? docs.
- `git restore --staged -- docs/testing/2026-11-07_evidence-media-build-10/images`:
  b? c?c ?nh m?i kh?i index, gi? nguy?n10 file tr?n ??a; kh?ng x?a/reset/rebase/stash.
- C?p nh?t [README run](../testing/2026-11-07_evidence-media-build-10/README.md): ?nh local-only,
  clone m?i kh?ng c? absolute inspection_file; mu?n review pixel c?n chia s? nguy?n blob ri?ng.
- Kh?ng resize/n?n ?nh, kh?ng thay SHA c?, kh?ng n?i/t?t hook.
- Stage c?c file h??ng d?n/s?a ignore li?n quan ?? ng??i d?ng c? th? commit ti?p trong VS Code.

## Ki?m ch?ng

Tr??c s?a, SHA-256 c?a c?10 ?nh tr?ng t?n file. Sau s?a ki?m l?i file/hash kh?ng ??i v? index
kh?ng c?n ?nh t? th? m?c n?y. Kh?ng s?a `.pre-commit-config.yaml` ho?c m? ?ng d?ng.
?? ch?y t? root: `backend/.venv/Scripts/python.exe -X utf8 -m pre_commit run`.
T?t c? hook ?p d?ng Passed; hooks kh?ng c? file ph? h?p Skipped; exit code0.
Kh?ng g?i DeepSeek/Tavily, embedding, notebook ho?c ch?y l?i unit suite cho thay ??i ignore/t?i li?u.

## Ng??i d?ng l?m ti?p

Trong Source Control c?a VS Code, nh?p Conventional Commit message r?i b?m Commit l?i.
V? d?: `feat(agent): select sourced evidence images and validate builds`.
Gi? nguy?n PR v? develop v? quy tr?nh review. Kh?ng bypass hook b?ng `--no-verify`.
