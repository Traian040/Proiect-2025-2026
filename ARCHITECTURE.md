# Architecture: Local Search Engine (Iteration I)

This document describes the software architecture of the local search engine using the C4 (Context, Containers, Components, Code) hierarchical model created by Simon Brown. One of the main goals of this architecture is to clearly define the boundaries between modules so that, as new requirements arise, the cost of changes is minimized.

## 1. System Context (Level 1)
The context level illustrates the big picture of the system and how it interacts with its environment. The system is an information indexing and retrieval solution designed to run locally on the user's computer. The ultimate goal, achieved over several iterations, is to provide an extremely fast and responsive experience, where results appear as the user types.

* **User:** The person who interacts with the system to locate files based on name, textual content, and associated metadata.
* **System (Local Search Engine):** The central application that indexes files on the device (including documents, media, and binaries, although the current iteration focuses on text files) and returns relevant results.
* **File System (External System):** The primary data source that the application traverses to extract content and monitor changes.

---

## 2. Containers (Level 2)
The architecture is divided into two main containers, representing distinctly deployable units that separate the application's processing logic from the data storage mechanism. This high-level technology decision provides a solid foundation for future functionality.

* **Core Application (Python Engine):** An executable utility that orchestrates directory traversal and text cleaning. The system can be configured at runtime (for example, by setting file ignore rules, the root directory, and the report format), which gives it a high degree of flexibility.
* **SQLite DBMS:** Since designing a custom indexing format is beyond the scope of this project, this responsibility is delegated to a database management system. The relational database is configured with Full-Text Search (FTS) capabilities, which determines the efficient way in which data is processed at query time and allows for the correct functioning of multi-word searches.

---

## 3. Components (Level 3)
Going deeper into the Python application container, we identify the major structural blocks that provide the system's functionalities. These components are designed to ensure maximum code robustness.

* **CLI & Configuration Manager:** The component responsible for retrieving and validating the arguments entered by the user at system startup. This component also tracks the progress of the operation and generates a detailed execution report at the end of the indexing process.
* **Resilient File Crawler:** An essential component that recursively traverses the file system. It is defensively designed to gracefully handle edge cases, such as file permission issues, infinite loops created by symlinks, or database connection timeouts, ensuring continuous execution without causing the application to crash.
* **Incremental Indexer:** To guarantee excellent performance, the system performs incremental indexing. This module detects file changes and updates the database only with recently modified file records, thus avoiding the slow and inefficient reconstruction of the entire database on each run.
* **Document Parser & Preview Generator:** The module that takes text files, filters out unwanted data, and extracts every bit of important information. It preserves all available metadata (such as extensions, tags, and timestamps) for future use cases. It also automatically generates contextual previews of files (for example, the first 3 rows of a document), which are essential for user satisfaction at the time of search.

---
## 4. Code and Classes (Level 4)
At the most detailed level, the components are implemented through a series of classes and methods that follow the basic principles of object-oriented programming (OOP) and good software engineering practices, including a clean and modular coding style.

* **`class AppConfig:`** Encapsulates and validates runtime settings (paths, extension filters, `.gitignore` rules).
* **`class DatabaseHandler:`** Handles interaction with SQLite. The database schema design uses appropriate data types and indexes. This class contains the logic to write and execute efficient and well-structured SQL queries, required for both insertion and for generating results and previews.
* **`class FileSystemCrawler:`** Encapsulates the traversal logic and decouples specific methods for evaluating symlinks and handling I/O errors, delegating found files to the incremental indexer.
* **`class ContentExtractor:`** A class dedicated to transforming raw data into indexable data. It exposes functions for processing text and assembling metadata into a structured format before sending it to the `DatabaseHandler`.