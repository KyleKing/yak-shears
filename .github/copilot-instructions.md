Visual Vibe

- clean and minimal with whimsical accents
- font is clean and easy to read on Mobile and Desktop
- Be inspired by this color scheme from Welcome to the Jungle: #f7cf46 (primary accent), #f5f3ef (background), #000000 (text), #ffff (nav), and additional accent colors include #f19d71, #73c1e5, and #e99bc6
- Responsive for iPhone 14, iPad, and Desktop Monitor

Code

- Use Python 3.14 and best practices
- Be concise
- No comments
- No one letter variables
- Do not add dependencies unless absolutely necessary
- Follow YAGNI
- Prefer implementing features in server side Python when possible. Use Alpine.js and Alpine-Ajax for interactivity
- Keep CSS minimal and scoped to component. Use default styling whenever possible
- The whole page should not be larger than 14Kb
- Support recent versions of FireFox desktop and Safari mobile browsers

Component: Note Editor

- Indicates spelling and grammar mistakes
- Pasted links are auto-formatted as markdown
- When editing a bulleted or numbered list, there is logic to intellegently indent the current item right or left. On Desktop this is with Tab and Shift+Tab and on mobile, there are buttons added to the keyboard. The indentation is in increments of four spaces, can't be deeper than the parent item, and (TBD - adds a new line above when indenting and removes when out denting)
- When typing enter from a bulleted or numbered list, the next line is automatically started with a continuation with matching indentation
- Supports toggling italic and bold on the selected text. On mobile, the keyboard is extended with buttons to apply bullet or italic to highlighted text

Component: Note Preview

- Indicates spelling and grammar mistakes
- Renders with djot library (`<script src="https://unpkg.com/@djot/djot@0.2.5/dist/djot.js"></script>` and `djot.renderHTML(djot.parse("- _example_"))`)

Component: Search

- Inspired by Telescope for nvim
- There is a text input, which is full width
- There is sidebar with is 1/2 width and a note preview
- The search sidebar shows each matched note with an abbreviated preview
- The search preview highlights what was matched during the search
- Search can either be a full page or a modal triggered by a button on the keyboard in mobile or ctrl-p on desktop

Page: Login

- Basic username/password if no valid session credentials were found
- Credentials last for 7 days
- Login goes to last URL before redirect

Page: View Notes

- URL is `/`
- Preview each note in rectangle with any metadata and any content that will fit
- Rectangles are wrapped with flexbox for responsiveness
- Clicking on a note opens the Note Page

Page: Note Page

- URL is `/note/<note-title>`
- There is a button to go back to `/`
- On mobile, defaults to Note Editor component full screen. If the screen is wide enough, the preview is shown side-by-side
- There is a button to toggle between Editor and Preview components
- There is a feature to link notes (TBD)
- There is a feature to see similar notes (TBD)
- There is a feature to support configuring note metadata during edit and to view when viewing (TBD)

Pending ideas

- best tiny model for plain text RAG (https://www.baseten.com/blog/the-best-open-source-embedding-models/#the-best-reward-model-allanai-llama-31-tulu-3-8b-reward) or run something slightly better on my laptop? For the latter, would track new and modified files removed from RAG until I can next ingest them from my laptop.
