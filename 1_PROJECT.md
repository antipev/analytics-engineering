# Analytics engineering

`Analytics engineer` takes raw, messy data and transforms it into clean, reliable, and well-structured datasets so that companies can solve business problems accurately.

## Objective
A practical demonstration of analytics engineering: structured, tested, and version-controlled data processing built to solve real business problems.


### Project 1 Overview (SOAR)

* **Situation:**

XKCD publishes new comics three times a week (Monday, Wednesday, Friday) and has been running since 2005. The comics cover a huge variety of topics, including:
  * **Technology & Computers:** Coding, software bugs, security passwords, automation, and the rise of artificial intelligence.
  * **Science & Math:** Physics, space exploration, statistics, data visualization, and biology.
  * **Geek Culture & Sci-Fi:** Video games, movies, internet culture, and nerdy humor.
  * **Everyday Life:** Relationships, social awkwardness, philosophy, and human quirks.


Source 1: https://xkcd.com/
          https://xkcd.com/about/
          An interface for automated systems to access comics and metadata:
          the JSON interface, at URLs like https://xkcd.com/info.0.json (current comic) and https://xkcd.com/614/info.0.json (comic #614).

* **Obstacle:**
There was no automated system to automatically collect these comics, save them to a database, clean them up for reporting, and share the final results with clear documentation and presentation slides.

* **Why?**  
    **The Business Problem:** A trend-tracking firm wants to monitor how public discourse around technology, science, and pop culture shifts over two decades. 

* **Why?**  
    Specifically, the goal is to understand shifting public interests and desires regarding **video games** and gaming culture.

* **Why?**  
    To identify potential directions for game development with a high chance of adoption, minimizing financial risk and maximizing the likelihood of success.

* **The Solution:**  
    Analyzing historical text data from XKCD allows researchers to track how specific tech keywords and cultural themes evolved year by year. Once the data is collected, AI agents consume it to automatically produce deep trend analyses and strategic insights—which are then directly used to draft the Product Development Plan (PDP) and guide future game design concepts.



* **Action:**
Built a complete data project from scratch. I set up version control, wrote code to fetch the comics, stored them in a database, cleaned the data for analysis, and created full documentation and presentation slides.

* **Result:**
Created a working, automated system that turns messy web data into clean, organized information ready for reports and presentations.

