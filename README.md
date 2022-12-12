

# **Profesia CLI** 

### Python CLI which enables querying jobs from [Profesia.sk](https://www.profesia.sk)

---

#### Features:
- Query for jobs
- Filter out title 
- Select salary range
- Export results to csv


#### How to use
1. ```git clone git@github.com:tomastoth/profesia-cli.git```
2. ``` cd profesia-cli```
3. ``` poetry install```
4. ``` playwright install```
5. ``` python3 app.py -k python -min 2000 -any medior junior -none senior```


#### CLI arguments
```
-k -> list of keywords to search for
-min -> min monthly salary in Euros
-max -> max monthly salary in Euros
-all -> list of words title needs to contain all these words
-any -> list of words title needs to contain any of these words
-none -> list of words title must not contain any of these words
-b -> True / False whether browser should be visible or not
```



Please notice the license. Author is not responsible for what you do with the code.
The code is released solely for educational purposes.
