# HTTP gameplay diagnostic review

AI-assisted review material; not human cross-review or semantic proof.

## IB-GS-061 / auto

Moonveil: đòn nhẹ và đòn nặng của Transient Moonlight khác nhau về hướng đánh và tầm ra sao?

Expected rubric: Đòn nhẹ quét ngang có projectile tầm ngắn; đòn nặng bổ dọc có projectile tầm trung. Không suy các con số damage hiện tại.

HTTP: 200 / ok

Đòn nhẹ của Transient Moonlight là một cú quét kèm sóng ánh sáng tầm ngắn, còn đòn nặng là cú chém từ trên xuống với sóng tầm trung, nên đòn nặng vươn xa hơn rõ rệt [1]. Đòn nhẹ thường nhanh hơn và quét rộng hơn, trong khi đòn nặng đánh một mục tiêu và khó lăn tránh thẳng ra sau hơn; dù vậy, cả kỹ năng vẫn hiệu quả nhất ở cự ly cận chiến vì lúc đó cả lưỡi kiếm lẫn sóng phép đều có thể trúng [1].

### [1] Moonveil

https://eldenring.wiki.gg/wiki/Moonveil#Notes

```text
The Unique Skill: Transient Moonlight is the regular Skill: Unsheathe but with added projectiles: a short-ranged one for the light attack sweep and a mid-ranged one for the heavy attack overhead slash.
The skill is useful in roughly the same ways that Unsheathe is, meaning that the light attack follow-up is generally slightly quicker and much wider in exchange for being slightly weaker, while the heavy attack follow-up hits a single target slightly harder and is slightly more difficult to roll directly away from.
One stark difference is that the different attacks are much less dissimilar, with the light attack follow-up having less of a damage difference (22% less for Unsheathe, 10% less for Transient Moonlight) and much less of a Stance damage difference (50% less for Unsheathe, 8% less for Transient Moonlight).
While this does give the weapon some more reach (though mostly with the heavy attack follow-up), the skill is still the most effective at melee range since that means both the weapon and the magic waves can hit the target.
The skill's heavy attack follow-up has a weird interaction with jumping players and deals a lot less damage against them for some reason.
While a hybrid Intelligence/Dexterity build gains the highest total Attack Power a pure Intelligence build only loses about 2% total Attack Power in exchange for the skill's projectiles getting 13% higher Attack Power, making the latter generally preferable.
```

Trace assessment: `{'status': 'sufficient', 'reason': 'assessed', 'decision': 'local_sufficient'}`

## IB-GS-092 / auto

Does the stat spread 40 Vigor, 20 Mind, 20 Endurance, 12 Strength, 18 Dexterity, 53 Intelligence, 8 Faith and 8 Arcane match level 100 by the sum-minus-79 rule?

Expected rubric: The sum is 179, so it matches level 100 arithmetically. This does not prove optimality, damage or weapon eligibility.

HTTP: 200 / ok

Yes — that spread adds up to 179, and with the level rule (sum of the eight attributes minus 79) that comes out to level 100 [1].

### [1] Attribute point accounting

https://eldenring.wikidot.com/stats

```text
A character's level equals the sum of the eight primary attributes minus 79. Thus the target attribute sum is level + 79. Vigor affects HP; Mind affects FP; Endurance affects stamina and equip load. Arithmetic does not establish optimality.
```

Trace assessment: `{'status': 'sufficient', 'reason': 'assessed', 'decision': 'local_sufficient'}`

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

Moonveil yêu cầu một tay Strength 12, Dexterity 18 và Intelligence 23 [3]. Samurai khởi đầu với Str 12, Dex 15, Int 9, nên bạn đã đủ Str, chỉ cần thêm 3 Dex để chạm 18 và đẩy Int từ 9 lên 23 [5].

Với Transient Moonlight, hướng Int thuần chỉ mất khoảng 2% tổng Attack Power so với build lai Int/Dex, nhưng đổi lại sóng kiếm được cộng khoảng 13% lực, nên nhìn chung Int-heavy là lựa chọn tốt hơn cho PvE [2]. Vì vậy cứ giữ Dex đúng mức yêu cầu rồi dồn phần còn lại vào Intelligence.

Ở level 100, tổng tám chỉ số của bạn là 179 điểm [4]. Trừ phần tối thiểu cho yêu cầu vũ khí, phần lớn nên chia cho Vigor, một ít Mind và Endurance vừa đủ mặc giáp/né, rồi đổ vào Int — đây là hướng gợi ý chứ không phải một con số tối ưu đã kiểm chứng.

Mình chưa thể xác nhận quy tắc respec nên không đưa ra bảng tám chỉ số chính xác; nếu bạn nói rõ có được đổi chỉ số tự do hay không, mình siết con số cụ thể hơn.

### [2] Moonveil

https://eldenring.wiki.gg/wiki/Moonveil#Notes

```text
The Unique Skill: Transient Moonlight is the regular Skill: Unsheathe but with added projectiles: a short-ranged one for the light attack sweep and a mid-ranged one for the heavy attack overhead slash.
The skill is useful in roughly the same ways that Unsheathe is, meaning that the light attack follow-up is generally slightly quicker and much wider in exchange for being slightly weaker, while the heavy attack follow-up hits a single target slightly harder and is slightly more difficult to roll directly away from.
One stark difference is that the different attacks are much less dissimilar, with the light attack follow-up having less of a damage difference (22% less for Unsheathe, 10% less for Transient Moonlight) and much less of a Stance damage difference (50% less for Unsheathe, 8% less for Transient Moonlight).
While this does give the weapon some more reach (though mostly with the heavy attack follow-up), the skill is still the most effective at melee range since that means both the weapon and the magic waves can hit the target.
The skill's heavy attack follow-up has a weird interaction with jumping players and deals a lot less damage against them for some reason.
While a hybrid Intelligence/Dexterity build gains the highest total Attack Power a pure Intelligence build only loses about 2% total Attack Power in exchange for the skill's projectiles getting 13% higher Attack Power, making the latter generally preferable.
```

### [3] Moonveil requirements

https://eldenring.wiki.gg/wiki/Moonveil

```text
Moonveil's listed one-handed requirements are Strength 12, Dexterity 18 and Intelligence 23. Requirements are distinct from scaling, recommended stats and damage; this does not establish latest-patch damage.
```

### [4] Attribute point accounting

https://eldenring.wikidot.com/stats

```text
A character's level equals the sum of the eight primary attributes minus 79. Thus the target attribute sum is level + 79. Vigor affects HP; Mind affects FP; Endurance affects stamina and equip load. Arithmetic does not establish optimality.
```

### [5] Samurai starting attributes

https://wiki.eso-ui.com/index.php/Elden_Ring:Samurai

```text
Samurai starts at level 9 with Vigor 12, Mind 11, Endurance 13, Strength 12, Dexterity 15, Intelligence 9, Faith 8, Arcane 8. These are starting values, not a recommended final build.
```

Trace assessment: `{'status': 'partial', 'reason': 'assessed', 'decision': 'local_partial'}`
