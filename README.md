# Student work · Catalina Ospina León

This is the website: **https://catalina-artdesign-teach.github.io**

Everything on the site comes from the folders here. When you add or change something, GitHub rebuilds the site by itself. It takes about **2–3 minutes** to appear.

| Folder or file | What it is |
|---|---|
| `year-7`, `year-8`, `year-9` | One folder per project, inside its year |
| `settings.txt` | Your name, the Home title, the year labels, the colours and the contact form key |
| `home.txt` | The paragraph on the Home page |
| `about.txt` | The title and text of the About page |
| `photo.jpg` | Your photo on the About page |
| `site-engine` | The machinery that builds the site. You don't need to touch it |

---

## Add a new project

**1. Create the text file**

1. Open the year folder, for example `year-8`.
2. Click **Add file → Create new file**.
3. In the name box, type a number, a short name, a slash, and `project.txt`, for example:

   `04-pop-art/project.txt`

   Typing the `/` creates the new folder. Use a number **higher** than the last project in that year: the highest number is shown first. Use only letters, numbers and dashes in the name, no spaces.
4. Paste this and fill it in:

   ```
   title: Pop Goes the Everyday
   keyword: Pop Art
   subject: Art & Design
   skills: Pop Art, Flat colour, Repetition, Collage
   school year: 2026-27

   Write the paragraph about the project here: what students learn,
   what they research and what they make.
   ```

   - **title**: the project's name.
   - **keyword**: one or two words. It appears on the square tile when the mouse goes over it; two words go on two lines. Short words (up to 6–7 letters) look best.
   - **subject** (optional): a small label above the project title, for example `Design · Computing`. Leave the line out and nothing shows.
   - **skills**: separated by commas. These become the tags in the coloured box.
   - **school year**: not shown on the site for now.
   - Then **one empty line**, and the paragraph. About 50–70 words fits best.
5. Click **Commit changes…**, then **Commit changes** again.

The project won't appear yet: it is waiting for its photos.

**2. Add the photos**

1. Open the new folder (`04-pop-art`).
2. Click **Add file → Upload files**.
3. Drag in the photos, straight from your phone or computer. HEIC (iPhone), JPG and PNG are all fine. The site converts and resizes them, and removes the location and camera details from each photo.
4. Click **Commit changes**.

Wait 2–3 minutes and the project is on the site.

**Good to know**

- Photos appear in the gallery in file-name order; for iPhone photos, that's the order you took them.
- The square tile uses the first photo. To choose a different one, rename that photo **cover** *before* uploading it (for example `cover.heic`). It becomes the tile and the first photo in the gallery.
- Upload your best 6–12 photos per project rather than all of them. It keeps the site fast and the folder small.

---

## Change something

- **Edit a project's text:** open its `project.txt`, click the **pencil** icon, change the text, then **Commit changes**.
- **Remove a photo:** open the photo, click **⋯** (top right) → **Delete file**, then **Commit changes**.
- **Remove a whole project:** open the project's folder, click **⋯** (top right) → **Delete directory**, then **Commit changes**.
- **Change the order:** change the number at the start of the folder name. Highest number = shown first.
- **Change your name, the Home title, the year labels or the colours:** edit `settings.txt` the same way. Each year has its own colour; `main colour` is used on Home and About. Colours are hex codes like `#FF5A36`; you can find codes at https://htmlcolorcodes.com.
- **Edit the Home paragraph:** edit `home.txt`. Keep it to about 30–50 words so the Home page fits on one screen.
- **Edit the About page:** edit `about.txt`. The `title:` line is the big heading; the first paragraph is shown slightly larger. Leave an empty line between paragraphs.
- **Change your photo:** upload a new photo named `photo` (JPG, PNG or HEIC) and delete the old one. The site crops it into the round shape by itself.

---

## Things that work by themselves

- **Link previews:** when you paste a link to the site into WhatsApp, LinkedIn, Teams or Outlook, a card with your name and the newest projects appears. Each year page has its own card, in its colour. They update when you add projects.
- **Line breaks:** "I", "a" and numbers are kept on the same line as the next word, so they never sit alone at the end of a line.
- **Contact form:** messages arrive in the email you registered with Web3Forms (https://web3forms.com). Click Reply in your email to answer the sender. The key is the `contact form key:` line in `settings.txt`; if that line is empty, the form shows that it isn't set up yet.

---

## Before you share the link

Delete the three **example** projects (the folders whose names contain `example`). They are made-up projects with placeholder pictures.

---

## If something goes wrong

If a project has a problem (for example the `keyword:` line is missing), **the site is not updated, and the previous version stays online**. GitHub sends you an email saying the run failed.

To see what to fix:

1. Click the **Actions** tab at the top of this page.
2. Click the run with the red ✗.
3. The page lists each problem, for example:
   `year-8/04-pop-art/project.txt: the 'keyword:' line is missing or empty.`

Fix it, commit, and the site updates by itself. Every change is saved in the history, so anything can be undone.

---

## Privacy

- This folder is **public**: anyone who finds it can see the files. The site asks search engines not to list it, but that is a request, not a lock. Only upload what you're happy for anyone to see.
- Never upload photos showing students' faces or names.
- The contact form asks for a name and an email address, which go only to your inbox, through Web3Forms. The form says they are only used to reply.

---

## One-time setup (already done once the site is live)

1. The repository must be called exactly `catalina-artdesign-teach.github.io` and be **Public**.
2. **Settings → Pages → Build and deployment → Source:** choose **GitHub Actions**.
3. To rebuild by hand: **Actions → Publish site → Run workflow**.
