import re


#basic component interface
class QueryBuilder:
    def build(self, query: str) -> str:
        raise NotImplementedError("Must implement build method")


#concrete component
class BaseQueryBuilder(QueryBuilder):
    def build(self, query: str) -> str:
        #return the query as is
        return query.strip()


#basic decorator
class QueryDecorator(QueryBuilder):
    def __init__(self, wrapped: QueryBuilder):
        self.wrapped = wrapped

    def build(self, query: str) -> str:
        return self.wrapped.build(query)


#concrete decorator
class SanitizationDecorator(QueryDecorator):
    def build(self, query: str) -> str:
        base_query = super().build(query)
        #strip out all non-alphanumeric characters
        return re.sub(r'[^\w\s]', '', base_query)


class SynonymDecorator(QueryDecorator):
    def __init__(self, wrapped: QueryBuilder):
        super().__init__(wrapped)
        #define standard synonyms
        self.synonyms = {
            "img": "img OR image OR photo",
            "doc": "doc OR document OR text",
            "dir": "dir OR directory OR folder",
            "err": "err OR error OR exception"
        }

    def build(self, query: str) -> str:
        base_query = super().build(query)
        words = base_query.split()
        expanded_words = []

        for w in words:
            lower_w = w.lower()
            if lower_w in self.synonyms:
                #wrap to make sure that it's a valid FTS5 query
                expanded_words.append(f"({self.synonyms[lower_w]})")
            else:
                expanded_words.append(w)

        return " ".join(expanded_words)


class LogicDecorator(QueryDecorator):
    def build(self, query: str) -> str:
        base_query = super().build(query)
        processed = []
        #tokenize the query separating words, operators, and parentheses
        tokens = re.findall(r'\(|\)|OR|AND|NOT|\w+', base_query)

        for token in tokens:
            if token in ("OR", "AND", "NOT", "(", ")"):
                #lleave parentheses and operators alone
                processed.append(token)
            else:
                #add wildcard to search tera for prefix matching
                processed.append(f"{token}*")

        #join with spaces
        return " ".join(processed)