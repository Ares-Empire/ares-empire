# Aresium policy insertions — prepared 2026-10-26, not published

Apply these instructions to `../datenschutz.html` and `../privacy.html` only when Aresium opens to other people.
The two fragments are body HTML, matching the existing `<h3>` / `<p>` markup. Section 6 receives the fragments;
sections 7–11 keep their numbers. No live policy file was changed by this brief.

The processing described is the agreed phone mode, including the optional server/Groq route. It is planned,
not verified implementation. Complete the opening checklist in [the inventory](../../../docs/PRIVACY.md) before
inserting it. In particular, verify ZDR, no content in logs, explicit consent, the third-party data issue, and
the recipient identity and transfer chain below. Provider and legal sources, all checked **2026-10-26**, are
listed in that file's “Opening Aresium: legal check” section; G1–G7 support the provider statements here and in
the fragments, L1–L11 support the legal statements. Direct sources (checked **2026-10-26**):
[retention/ZDR](https://console.groq.com/docs/your-data),
[DPA/SCCs](https://console.groq.com/docs/legal/customer-data-processing-addendum),
[agreement/entities/training](https://console.groq.com/docs/legal/services-agreement),
[official DPF list](https://www.dataprivacyframework.gov/list),
[Commission adequacy decisions, including the UK](https://commission.europa.eu/law/law-topic/data-protection/international-dimension-data-protection/adequacy-decisions_en).
The public text does not describe the owner's private mode.

## Serving check

`webauth/legal.py` has a fixed `PAGES` mapping: only the six named legal/contact URLs are rendered. None points
into `drafts/`; `legal.render('/legal/drafts/aresium.de.html', ...)` returns `None`, including in preview mode.
`DRAFT_MARKERS` (`[ADDRESS]`, `[lead to confirm]`) protect mapped pages, not arbitrary files.

**There is a separate exposure path:** `webauth/server.py`, `Handler.do_GET` / `do_HEAD`, falls through to
`SimpleHTTPRequestHandler` after the login gate. These files are under its `web/` root. An authenticated hub
user could therefore fetch `/legal/drafts/aresium.de.html`, `/legal/drafts/aresium.en.html` or this README if
this worktree's `web/` is deployed wholesale. They are not in `OPEN_PATHS`, so they are not public legal routes,
but it would be false to say they cannot be served at all. No serving code was changed, as requested. The lead
must exclude `web/legal/drafts/` from deployed static files or separately fix static serving before deployment.
A marker in a fragment would not fix this static path.

## Recipient identity and transfer gate

The plan calls the provider **Groq, Inc., USA**. The current public Services Agreement instead names **Groq UK
Limited** for EEA customers, and **Groq LLC** for most other customers (G3, definition “Groq Contracting Party”).
The prepared primary insertion below follows those current EEA terms. The existing account's accepted contract
was not accessible in this public-only check. Patrik must check it and save the applicable agreement/DPA outside
the repo. If it is still with Groq, Inc., use the exact alternative recipient and transfer text below. Do not
silently treat these legal entities as interchangeable.

G1 establishes US storage if content is retained; G2 allows US and other processing countries. Public pages do
not establish the inference region or full onward-transfer chain for this account. Section 8's prepared text
covers the UK contracting party and US processing. Confirm that chain before publication; add any other actual
countries and their safeguards if the provider confirms them. An active Groq DPF participant was not found in
the official list (G5); these drafts rely on SCCs for US transfers, subject to the transfer assessment.

## German: `web/legal/datenschutz.html`

1. Replace exactly `<p class="stand">Stand: 25. Oktober 2026</p>` with
   `<p class="stand">Stand: 26. Oktober 2026</p>`. If publication happens later, use the actual revision date.

2. Insert the complete contents of `aresium.de.html` after this exact paragraph in section 6, before section 7:

```html
<p>Die Apps enthalten keine Analyse-, Werbe- oder Tracking-Funktionen.</p>
```

3. In section 5 replace these two sentences (leave the following sentence about ending access to one app intact):

```html
Dabei werden
das Konto und alle zugehörigen Daten in allen Diensten gelöscht.
```

with:

```html
Dabei werden
das Konto und die zugehörigen Daten auf den Servern der Dienste gelöscht. Die lokalen Finanzdaten von Aresium
werden auf dem jeweiligen iPhone gelöscht, sobald die App die Kontolöschung verarbeitet; für ein nicht
erreichbares Gerät ist keine sofortige Fernlöschung möglich. Gerätesicherungen und exportierte Dateien sind
davon nicht erfasst (Abschnitt 6).
```

This is an implementation gate: the app must actually process account deletion this way; check an offline device
and subsequent sign-in failure. Do not promise a remote wipe the server cannot perform.

4. In section 7 insert after the netcup `<li>`:

```html
  <li>Groq UK Limited, Vereinigtes Königreich: automatische Kategorisierung von Zahlungen bei aktivierter
    automatischer Sortierung in Aresium (GroqCloud; Verarbeitung auch in den USA; Auftragsverarbeitung nach
    Art. 28 DSGVO),</li>
```

If Patrik confirms the applicable recipient remains Groq, Inc., replace that new `<li>` with this exact alternative:

```html
  <li>Groq, Inc., USA: automatische Kategorisierung von Zahlungen bei aktivierter automatischer Sortierung
    in Aresium (GroqCloud; Auftragsverarbeitung nach Art. 28 DSGVO),</li>
```

5. Insert after the existing paragraph in section 8:

```html
<p>Für die automatische Sortierung in Aresium werden Daten an Groq im Vereinigten Königreich und zur
Verarbeitung auch in die USA übermittelt. Für das Vereinigte Königreich besteht ein Angemessenheitsbeschluss
der Europäischen Kommission (Art. 45 DSGVO). Für die Übermittlung in die USA werden die Standardvertragsklauseln
der Europäischen Kommission im Datenverarbeitungszusatz von Groq verwendet (Art. 46 Abs. 2 lit. c DSGVO).
Eine Kopie der vereinbarten Garantien kann beim Verantwortlichen angefordert werden; der
<a href="https://console.groq.com/docs/legal/customer-data-processing-addendum">Datenverarbeitungszusatz
von Groq</a> ist auch online verfügbar.</p>
```

For the confirmed Groq, Inc. alternative, replace only that new paragraph with:

```html
<p>Für die automatische Sortierung in Aresium werden Daten an Groq in die USA übermittelt. Grundlage sind
die Standardvertragsklauseln der Europäischen Kommission im Datenverarbeitungszusatz von Groq
(Art. 46 Abs. 2 lit. c DSGVO). Eine Kopie der vereinbarten Garantien kann beim Verantwortlichen angefordert
werden; der <a href="https://console.groq.com/docs/legal/customer-data-processing-addendum">Datenverarbeitungszusatz
von Groq</a> ist auch online verfügbar.</p>
```

6. In section 9 insert after the first paragraph (ending `bis 6 genannt.</p>`):

```html
<p>Für die übermittelten Inhalte der automatischen Sortierung in Aresium gilt Abschnitt 6: keine Speicherung
auf dem Aresium-Server und keine Aufbewahrung der Ein- und Ausgaben durch Groq für Zuverlässigkeits- oder
Missbrauchsprotokolle bei aktiviertem „Zero Data Retention“. Diese Inhalte gelangen nicht in die nachfolgend
beschriebenen Server-Sicherungen. Lokale Finanzdaten bleiben auf dem iPhone bis zur Löschung in der App;
Gerätesicherungen und Exporte verwalten Sie selbst.</p>
```

7. In section 10 insert immediately before `<p><strong>Widerspruchsrecht:</strong>`:

```html
<p><strong>Widerruf der Einwilligung:</strong> Sie können eine Einwilligung jederzeit mit Wirkung für die
Zukunft widerrufen (Art. 7 Abs. 3 DSGVO). Für die automatische Sortierung in Aresium genügt das Ausschalten
der Funktion in den Einstellungen der App. Die Rechtmäßigkeit der Verarbeitung vor dem Widerruf bleibt
unberührt. Die übrigen Funktionen von Aresium können weiterhin genutzt werden.</p>
```

8. In section 11 replace exactly:

```html
Eine automatisierte
Entscheidungsfindung einschließlich Profiling (Art. 22 DSGVO) findet nicht statt.
```

with:

```html
Die automatische Sortierung in Aresium analysiert die übermittelten Zahlungsangaben und ordnet sie
Kategorien zu. Sie ist freiwillig; ohne Einwilligung werden keine Zahlungsangaben für diese Funktion
übermittelt. Eine ausschließlich automatisierte Entscheidung mit rechtlicher oder ähnlich erheblicher
Wirkung im Sinne von Art. 22 DSGVO findet nicht statt.
```

## English: `web/legal/privacy.html`

1. Replace exactly `<p class="stand">Last updated: 25 October 2026</p>` with
   `<p class="stand">Last updated: 26 October 2026</p>`. If publication happens later, use the actual revision date.

2. Insert the complete contents of `aresium.en.html` after this exact paragraph in section 6, before section 7:

```html
<p>The apps contain no analytics, advertising or tracking functions.</p>
```

3. In section 5 replace exactly:

```html
the account and all
associated data are then deleted in every service.
```

with:

```html
the account and associated data on the services' servers are then deleted. Aresium's local financial data
are deleted on each iPhone when the app processes the account deletion; an unreachable device cannot be
wiped remotely immediately. Device backups and exported files are not included (section 6).
```

Apply the same deletion implementation gate as for German step 3.

4. In section 7 insert after the netcup `<li>`:

```html
  <li>Groq UK Limited, United Kingdom: automatic categorisation of payments when automatic sorting is enabled
    in Aresium (GroqCloud; processing also in the USA; processing on behalf under Art. 28 GDPR),</li>
```

For the confirmed Groq, Inc. alternative, use this exact `<li>` instead:

```html
  <li>Groq, Inc., USA: automatic categorisation of payments when automatic sorting is enabled in Aresium
    (GroqCloud; processing on behalf under Art. 28 GDPR),</li>
```

5. Insert after the existing paragraph in section 8:

```html
<p>For automatic sorting in Aresium, data are transferred to Groq in the United Kingdom and also to the
USA for processing. The European Commission has adopted an adequacy decision for the United Kingdom
(Art. 45 GDPR). Transfers to the USA use the European Commission's standard contractual clauses
incorporated in Groq's data processing addendum (Art. 46(2)(c) GDPR). You can request a copy of the agreed
safeguards from the controller; <a href="https://console.groq.com/docs/legal/customer-data-processing-addendum">Groq's
data processing addendum</a> is also available online.</p>
```

For the confirmed Groq, Inc. alternative, use this exact paragraph instead:

```html
<p>For automatic sorting in Aresium, data are transferred to Groq in the USA on the basis of the European
Commission's standard contractual clauses incorporated in Groq's data processing addendum
(Art. 46(2)(c) GDPR). You can request a copy of the agreed safeguards from the controller;
<a href="https://console.groq.com/docs/legal/customer-data-processing-addendum">Groq's data processing
addendum</a> is also available online.</p>
```

6. In section 9 insert after the first paragraph (ending `in sections 2 to 6.</p>`):

```html
<p>Section 6 applies to the transmitted content of automatic sorting in Aresium: no storage on the Aresium
server and no retention of inputs and outputs by Groq for reliability or abuse monitoring with Zero Data
Retention enabled. These contents are not included in the server backups described below. Local financial
data remain on your iPhone until deleted in the app; you manage your own device backups and exports.</p>
```

7. In section 10 insert immediately before `<p><strong>Right to object:</strong>`:

```html
<p><strong>Withdrawal of consent:</strong> You can withdraw consent at any time with effect for the future
(Art. 7(3) GDPR). For automatic sorting in Aresium, switch off the feature in the app's settings. Withdrawal
does not affect the lawfulness of processing before it was withdrawn. You can continue to use Aresium's
other functions.</p>
```

8. In section 11 replace exactly:

```html
No automated decision-making, including profiling (Art. 22 GDPR),
takes place.
```

with:

```html
Automatic sorting in Aresium analyses the transmitted payment details and assigns categories. It is
optional; without consent, no payment details are transmitted for this feature. No solely automated
decision with legal or similarly significant effects within the meaning of Art. 22 GDPR takes place.
```

## Consent and implementation handoff

The policy alone does not obtain consent. Keep the single switch, off by default, and show the data fields,
netcup/Groq, US processing, transient content processing, sensitive-data warning, optional nature and withdrawal
next to it, with a link to the policy. Use an explicit statement, for example:

> Durch Einschalten willigen Sie ausdrücklich ein, dass nicht zugeordnete Zahlungen (Datum, Betrag, Buchungstext,
> Zahlungspartner, zufällige Referenz) und Ihre Kategorienamen über den Server in Deutschland an Groq zur
> KI-Sortierung, auch in den USA, gesendet werden. Dies umfasst Angaben zu Ihrer Gesundheit, Religion oder
> Gewerkschaftszugehörigkeit, soweit sie daraus hervorgehen. Die Zahlungsinhalte werden nur zur Beantwortung
> verarbeitet; bei Groq ist Zero Data Retention aktiviert. Die Funktion ist freiwillig. Ausschalten widerruft
> die Einwilligung für künftige Anfragen; die bisherige Verarbeitung bleibt rechtmäßig. Aresium bleibt ohne
> diese Funktion nutzbar. Weitere Angaben: Datenschutzerklärung.

> By switching this on, you explicitly consent to sending unassigned payments (date, amount, booking text,
> counterparty, random reference) and your category names through the server in Germany to Groq for AI sorting,
> including in the USA. This includes information about your health, religion or trade union membership where
> revealed by these details. Payment content is processed only to answer the request; Groq's Zero Data Retention
> is enabled. The feature is optional. Switching it off withdraws consent for future requests; prior processing
> remains lawful. You can still use Aresium without it. Further details: privacy policy.

This is proposed UI wording, not a new consent flow. Keep evidence of the wording/version and affirmative action
without retaining payment content; the evidence mechanism and retention still need to be decided. Disabling
must prevent future sends and queued retries. Do not promise recall of a request already transmitted.

**Open:** this consent covers the consenting user's data, not independent private counterparties' data. Resolve
their lawful basis, Article 14 notice/exemption, and any special-category information about them before enabling
the route. Update the draft if the resolution changes the transmitted fields. Likewise check the planned AI
header mapping: a header is not guaranteed to be free of personal data. See the internal legal check.
