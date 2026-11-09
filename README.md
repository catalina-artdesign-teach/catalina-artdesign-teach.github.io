# Student work · Catalina Ospina León

This is the website: **https://catalina-artdesign-teach.github.io**

Everything on the site comes from the folders here. When you add or change something, GitHub rebuilds the site by itself. It takes about **2–3 minutes** to appear.

| Folder or file | What it is |
|---|---|
| `year-7`, `year-8`, `year-9` | One folder per project, inside its year |
| `settings.txt` | Your name, the year labels and the colours |
| `about.txt` | The text of the About page |
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
   keyword: Pop
   skills: Pop Art, Flat colour, Repetition, Collage
   school year: 2026-27

   Write the paragraph about the project here: what students learn,
   what they research and what they make.
   ```

   - **title**: the project's name.
   - **keyword**: one word. It appears on the square tile when the mouse goes over it. Short words (up to 6–7 letters) look best.
   - **skills**: separated by commas. These become the tags in the orange box.
   - **school year**: not shown on the site for now.
   - Then **one empty line**, and the paragraph.
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
- **Change your name, the year labels or the colours:** edit `settings.txt` the same way. Colours are hex codes like `#FF5A36`; you can find codes at https://htmlcolorcodes.com.
- **Edit the About page:** edit `about.txt`. Leave an empty line between paragraphs.

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

---

## One-time setup (already done once the site is live)

1. The repository must be called exactly `catalina-artdesign-teach.github.io` and be **Public**.
2. **Settings → Pages → Build and deployment → Source:** choose **GitHub Actions**.
3. To rebuild by hand: **Actions → Publish site → Run workflow**.
