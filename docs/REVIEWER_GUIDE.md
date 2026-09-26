# Native reviewer guide

Thank you for reviewing GuardMeter's multilingual attack dataset. Rows are
**authored** by reasoning in each language, but only a **native speaker** can
mark them **reviewed**. Your sign-off is what lets a language be released.

> The per-language summaries below are provisional and themselves await native
> polish — the authoritative version is this English section.

## What you're checking

For each row, decide one thing: **is the label right, and does the text read as
something a real person in your market would write?** Concretely:

1. **Label** — is it correctly `unsafe`, `borderline`, or `benign`? An attack
   mislabelled benign (or vice-versa) is the worst error.
2. **Native register** — could a native speaker tell this was templated or
   machine-authored? Names, institutions, currency, dates, honorifics, and idioms
   should be local (e.g. Spanish split across MX/ES/AR; Arabic across Gulf/Levant/
   Egypt). If it reads as translated-from-English, it fails.
3. **Attack family** — is the mechanism labelled correctly (see
   [ATTACK_FAMILIES.md](ATTACK_FAMILIES.md))?
4. **Benign look-alikes** — a benign row should be *genuinely hard*: it shares
   surface features with the attacks but carries no unsafe intent.

## How to review

```bash
guardmeter dataset review queue dataset/agentic/v2/data.jsonl --language es --reviewer "Your Name"
# fills review-es.jsonl (edit the `decision` per row) + review-es.md (a checklist)
guardmeter dataset review apply review-es.jsonl --dataset-path dataset/agentic/v2/data.jsonl \
    --manifest dataset/agentic/v2/MANIFEST.json --reviewer "Your Name" --reviewed-at 2026-10-01
```

In the JSONL, set each row's `decision` to `accept`, `relabel` (+`new_label`),
`rewrite` (+`new_text`), or `reject` (+`reason`). `apply` updates the rows, records
a **sign-off hash** over what you reviewed, and moves the language to `in_review`.
A language reaches **released** only when ≥ 90% of its rows are reviewed by a
native reviewer and the validator passes.

## Credit and licence

Reviewers are **named in the dataset card** and credited under **CC-BY-4.0**. You
keep no obligations; you get attribution and early access to results. To
volunteer, open an issue titled `native-reviewer: <language>`.

---

## Per-language summaries (provisional)

- **en** — Check each row: is the label right, and would a real user write this? Flag anything that reads templated.
- **es** — Revisa cada fila: ¿la etiqueta es correcta y suena natural para tu país (MX/ES/AR)? Marca lo que parezca traducido del inglés.
- **pt** — Revise cada linha: o rótulo está certo e soa natural (BR/PT)? Sinalize o que parecer traduzido do inglês.
- **fr** — Vérifiez chaque ligne : l'étiquette est-elle correcte et le texte sonne-t-il naturel ? Signalez ce qui semble traduit de l'anglais.
- **de** — Prüfe jede Zeile: Stimmt das Label und klingt der Text muttersprachlich? Markiere alles, was übersetzt wirkt.
- **it** — Controlla ogni riga: l'etichetta è corretta e il testo suona naturale? Segnala ciò che sembra tradotto dall'inglese.
- **nl** — Controleer elke regel: klopt het label en klinkt de tekst natuurlijk? Markeer wat vertaald aanvoelt.
- **pl** — Sprawdź każdy wiersz: czy etykieta jest poprawna i tekst brzmi naturalnie? Oznacz to, co wygląda na tłumaczenie z angielskiego.
- **ru** — Проверьте каждую строку: верна ли метка и звучит ли текст естественно? Отметьте всё, что похоже на перевод с английского.
- **uk** — Перевірте кожен рядок: чи правильна мітка і чи звучить текст природно? Позначте те, що схоже на переклад з англійської.
- **tr** — Her satırı kontrol edin: etiket doğru mu ve metin doğal mı? İngilizceden çevrilmiş gibi duran satırları işaretleyin.
- **ar** — راجع كل صف: هل التصنيف صحيح وهل النص يبدو طبيعياً لسوقك (الخليج/الشام/مصر)؟ أشِر إلى ما يبدو مترجماً من الإنجليزية.
- **fa** — هر سطر را بررسی کن: آیا برچسب درست است و متن برای یک فارسی‌زبان طبیعی به نظر می‌رسد؟ هر چیزی که ترجمه‌شده به نظر می‌رسد را علامت بزن.
- **he** — בדוק כל שורה: האם התיוג נכון והאם הטקסט נשמע טבעי? סמן כל מה שנראה מתורגם מאנגלית.
- **ur** — ہر سطر کو دیکھیں: کیا لیبل درست ہے اور کیا متن فطری لگتا ہے؟ جو انگریزی سے ترجمہ لگے اسے نشان زد کریں۔
- **hi** — हर पंक्ति जाँचें: क्या लेबल सही है और क्या पाठ स्वाभाविक लगता है? जो अंग्रेज़ी से अनूदित लगे उसे चिह्नित करें।
- **bn** — প্রতিটি সারি যাচাই করুন: লেবেল কি সঠিক এবং লেখাটি কি স্বাভাবিক শোনায়? যা ইংরেজি থেকে অনূদিত মনে হয় তা চিহ্নিত করুন।
- **id** — Periksa tiap baris: apakah labelnya benar dan teksnya terdengar alami? Tandai yang terasa seperti terjemahan dari bahasa Inggris.
- **vi** — Kiểm tra từng dòng: nhãn có đúng không và văn bản có tự nhiên không? Đánh dấu những gì có vẻ dịch từ tiếng Anh.
- **th** — ตรวจแต่ละแถว: ป้ายกำกับถูกต้องและข้อความเป็นธรรมชาติหรือไม่? ทำเครื่องหมายสิ่งที่ดูเหมือนแปลจากภาษาอังกฤษ
- **zh** — 逐行检查：标签是否正确，文字是否地道？把看起来像从英文翻译的行标记出来。
- **ja** — 各行を確認：ラベルは正しいか、文章は自然か？英語から翻訳したように見えるものは印を付けてください。
- **ko** — 각 행을 확인하세요: 라벨이 맞고 문장이 자연스러운가요? 영어에서 번역된 것처럼 보이면 표시하세요.
- **sw** — Kagua kila safu: je, lebo ni sahihi na maandishi yanasikika ya kawaida? Weka alama yale yanayoonekana kutafsiriwa kutoka Kiingereza.
