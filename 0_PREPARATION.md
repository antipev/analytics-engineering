# Short step by step instruction

## 1. Starting place is your github

Go to your github and create repository.

My example:
```
https://github.com/antipev/analytics-engineering
```


## 2. Next place is your terminal

My example: Ubuntu

```
root@MSI:~#

```

Determine if you need to go to specific repo:
```
root@MSI:~# ls

cd /home/maxantipev/

```

Clone the repo locally
```
git clone https://github.com/antipev/analytics-engineering.git .
```

## 3. After that is your IDE
My example: Ubuntu, VS Code

launch VS Code:Open in VS Code.
```
cd analytics-engineering

code .
```

## 4.Create your first file:

VS Code, click the New File icon in the Explorer sidebar (or go to File > New File), name it 
 
My example:

```
0_PREPARATION.md, and type a quick title like # Short step by step instruction. Add text as needed
```


## 5.Stage and commit your changes

Open the terminal inside VS Code (Terminal > New Terminal) and run these commands to save your work to Git:

My example:

```
git add 0_PREPARATION.md
git commit -m "Initial commit"
git status

```

Running git status should show a clean working tree with no uncommitted changes.


## 6.Push your code to GitHub

Link your local repository to GitHub and push your work by running:

```
git branch -M main
git push -u origin main
```

If necessary
```
git commit --amend --reset-author -m "first commit"
git push -u origin main --force

```

Refresh your GitHub repository page in your browser to see your new 0_PREPARATION.md file uploaded.