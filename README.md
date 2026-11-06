# My Teams calendar

Every 4 hours, a free GitHub Action pulls game schedules from ESPN and rebuilds calendar files. Apple Calendar subscribes to them and stays up to date on its own, including time changes, TV channels and final scores.

## One-time setup (about 10 minutes)

1. **Make a public GitHub repo.** Sign in at github.com and click **New repository**. Name it `team-calendar`, set it to **Public**, and tick **Add a README**.
2. **Upload these files.** In the repo, choose **Add file → Upload files** and drag in everything from this folder, including the `.github` folder. On a Mac, press Cmd+Shift+. in Finder to show it. Then click **Commit changes**.
3. **Run it once.** Open the **Actions** tab and click **Update team calendars**, then **Run workflow**. After a minute or so a `calendars/` folder appears in the repo.
4. **Subscribe in Calendar on your Mac.** Choose **File → New Calendar Subscription** and paste:

   ```
   https://raw.githubusercontent.com/YOUR-GITHUB-USERNAME/team-calendar/main/calendars/all.ics
   ```

   Set **Auto-refresh** to *Every hour* and **Location** to *iCloud*, so the calendar syncs to your iPhone.

### Separate colors per team (optional)

Instead of `all.ics`, subscribe to each team's own file. Each one becomes its own calendar, so you can give it its own color:

`knicks.ics` · `bristol-city.ics` · `malaga.ics` · `ucla-football.ics` · `ucla-mbb.ics` · `ucla-wbb.ics` · `usc-wbb.ics`

## Adding or removing teams

Edit `teams.json` on GitHub. Each team needs ESPN's team id, which is the number in its ESPN URL. For example, espn.com/nba/team/_/name/ny/new-york-knicks uses id `18`. Leagues use ESPN's codes: `nba`, `nfl`, `mlb`, `nhl`, `eng.1`, `esp.1`, `usa.1`, `college-football`, `mens-college-basketball`, `womens-college-basketball`.

## Notes

- Bristol City includes FA Cup and League Cup games. Málaga includes Copa del Rey, and also checks Segunda División in case of relegation.
- Games without a confirmed kickoff time show up as all-day events. They update once the time is announced.
- GitHub can pause scheduled jobs in a repo that has had no activity for 60 days. If it emails you about that, click the link to keep the job running.
