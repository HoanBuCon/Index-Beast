# HTTP gameplay diagnostic review

AI-assisted review material; not human cross-review or semantic proof.

## GP-01:1 / auto

Chia chỉ số Moonveil

Expected rubric: Ask level/class then goal; resume original Moonveil request. Never search only PvE.

HTTP: 200 / ok

Level mục tiêu của bạn là bao nhiêu? Bạn chọn class khởi đầu nào?

Trace assessment: `None`

## GP-01:2 / auto

100, Samurai

Expected rubric: Ask level/class then goal; resume original Moonveil request. Never search only PvE.

HTTP: 200 / ok

Bạn chơi PvE hay PvP?

Trace assessment: `None`

## GP-01:3 / auto

PvE

Expected rubric: Ask level/class then goal; resume original Moonveil request. Never search only PvE.

HTTP: 200 / ok

Moonveil cần Strength 12, Dexterity 18 và Intelligence 23 để dùng một tay [1]. Với Samurai (bắt đầu level 9: Vigor 12, Mind 11, Endurance 13, Strength 12, Dexterity 15, Intelligence 9, Faith 8, Arcane 8) [3], lên level 100 nghĩa là tổng tám chỉ số phải bằng 179 [2], và vì respec không thể hạ chỉ số dưới mức gốc của class, mọi phân bổ đều phải tôn trọng các mức sàn đó [4].

Một ví dụ khả thi cho PvE thuần Moonveil (đây là gợi ý, không phải tối ưu đã kiểm chứng): ưu tiên Intelligence và Dexterity vì Moonveil là vũ khí lai Int/Dex, dồn phần còn lại cho Vigor/Mind/Endurance để sống sót và đủ FP dùng skill. Chỉ số cụ thể ở khối phân bổ bên dưới; bạn có thể chỉnh lại tùy theo việc bạn spam Transient Moonlight nhiều hay đánh cận chiến nhiều hơn [5].

Ví dụ phân bổ hợp lệ về điểm/requirements, chưa xác minh tối ưu:
Vigor 43 | Mind 18 | Endurance 20 | Strength 12 | Dexterity 24 | Intelligence 46 | Faith 8 | Arcane 8 [1][2][3][4]

Đây là một ví dụ hợp lệ về mặt số học và yêu cầu vũ khí, không phải build tối ưu; mình chưa thể xác nhận các mốc soft cap hay hiệu suất theo patch hiện tại.

### [1] Moonveil requirements

https://eldenring.wiki.gg/wiki/Moonveil

```text
Moonveil's listed one-handed requirements are Strength 12, Dexterity 18 and Intelligence 23. Requirements are distinct from scaling, recommended stats and damage; this does not establish latest-patch damage.
```

### [2] Attribute point accounting

https://eldenring.wikidot.com/stats

```text
A character's level equals the sum of the eight primary attributes minus 79. Thus the target attribute sum is level + 79. Vigor affects HP; Mind affects FP; Endurance affects stamina and equip load. Arithmetic does not establish optimality.
```

### [3] Samurai starting attributes

https://wiki.eso-ui.com/index.php/Elden_Ring:Samurai

```text
Samurai starts at level 9 with Vigor 12, Mind 11, Endurance 13, Strength 12, Dexterity 15, Intelligence 9, Faith 8, Arcane 8. These are starting values, not a recommended final build.
```

### [4] Respec baseline constraints

https://eip.gg/elden-ring/guides/how-to-respec/

```text
Respec redistributes available attributes without lowering character level. Attributes determined by the starting class cannot be reduced below their original values. All available attribute points must be spent.
```

### [5] Moonveil

https://eldenring.wiki.gg/wiki/Moonveil#Notes

```text
The Unique Skill: Transient Moonlight is the regular Skill: Unsheathe but with added projectiles: a short-ranged one for the light attack sweep and a mid-ranged one for the heavy attack overhead slash.
The skill is useful in roughly the same ways that Unsheathe is, meaning that the light attack follow-up is generally slightly quicker and much wider in exchange for being slightly weaker, while the heavy attack follow-up hits a single target slightly harder and is slightly more difficult to roll directly away from.
One stark difference is that the different attacks are much less dissimilar, with the light attack follow-up having less of a damage difference (22% less for Unsheathe, 10% less for Transient Moonlight) and much less of a Stance damage difference (50% less for Unsheathe, 8% less for Transient Moonlight).
While this does give the weapon some more reach (though mostly with the heavy attack follow-up), the skill is still the most effective at melee range since that means both the weapon and the magic waves can hit the target.
The skill's heavy attack follow-up has a weird interaction with jumping players and deals a lot less damage against them for some reason.
While a hybrid Intelligence/Dexterity build gains the highest total Attack Power a pure Intelligence build only loses about 2% total Attack Power in exchange for the skill's projectiles getting 13% higher Attack Power, making the latter generally preferable.
```

Trace assessment: `{'status': 'partial', 'reason': 'assessed', 'decision': 'local_partial'}`
