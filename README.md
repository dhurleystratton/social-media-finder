# Social Media Finder

A multi-platform tool for discovering social media accounts across various platforms.

## Overview

This project provides a modular framework for finding and verifying social media profiles across different platforms including Twitter/X, Instagram, and LinkedIn. It's designed with rate limiting, caching, and verification features to ensure reliable results.

## Features

- Multi-platform support (Twitter/X, Instagram, LinkedIn)
- Batch processing capability
- Result caching to minimize redundant requests
- Confidence scoring for matches
- Executive contact categorization utilities
- Email pattern prediction and verification
- Comprehensive rate limiting to respect platform policies

## Project Structure

social-media-finder/
├── platforms/       # Platform-specific modules
│   ├── twitter.py   # Twitter/X implementation
│   ├── instagram.py # Instagram implementation (future)
│   ├── linkedin.py  # LinkedIn implementation (future)
├── utils/           # Shared utilities
│   ├── rate_limiting.py  # Rate limiting logic
│   ├── verification.py   # Profile verification helpers
│   ├── caching.py        # Result caching
├── config/          # Configuration files
├── tests/           # Unit and integration tests

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/social-media-finder.git
cd social-media-finder

# Install dependencies
pip install -r requirements.txt
```

## Usage

Basic example (to be implemented):

```python
from platforms.twitter import TwitterFinder

# Initialize finder
finder = TwitterFinder(api_key="your_api_key")

# Find profiles
results = finder.find_profile(name="John Smith", additional_info={"location": "New York"})

# Process results
for result in results:
    print(f"Found profile: {result.url} (confidence: {result.confidence})")
```

### Executive Contact Categorization

```python
from utils import ContactIdentifier

identifier = ContactIdentifier()
contacts = [
    {"name": "Jane Smith", "title": "Chief Legal Officer", "source": "website"},
    {"name": "John Doe", "title": "Finance Director", "source": "linkedin"},
]
matched = identifier.categorize_contacts(contacts)
for m in matched:
    print(m.role, m.name, m.score)
```

### Email Pattern Prediction

```python
from utils import EmailPatternGenerator

generator = EmailPatternGenerator()
contact = {"name": "Jane Smith", "organization": "Example Fund"}
candidates = generator.generate_candidates(contact)
verified = generator.verify_emails(candidates)
best = generator.get_best_match(verified)
print(best.email, best.confidence)
```

### Testing Framework

The project ships with a small testing harness that can build reproducible
samples and exercise individual components or the entire discovery pipeline.

```python
from pathlib import Path
from utils import (
    TestFramework,
    OrganizationProcessor,
    WebsiteScraper,
    PublicFilingsFinder,
    ContactIdentifier,
    EmailPatternGenerator,
)

framework = TestFramework(
    full_dataset_path="tafthartley_union_trusts.csv",
    components={
        "csv_processor": OrganizationProcessor("tafthartley_union_trusts.csv"),
        "website_scraper": WebsiteScraper(rate_limit=0),
        "filings_finder": PublicFilingsFinder(local_dir=Path("filings")),
        "contact_identifier": ContactIdentifier(),
        "email_generator": EmailPatternGenerator(rate_limit=0),
    },
)

sample = framework.create_sample(size=5, random_seed=42)
component_results = framework.test_components(
    sample=sample,
    components=["website_scraper", "filings_finder"],
)
pipeline_results = framework.test_pipeline(
    sample=sample,
    target_roles=["General Counsel", "CFO"],
)
framework.generate_report(
    component_results=component_results,
    pipeline_results=pipeline_results,
    output_path="test_results.html",
)
```

## Roadmap

- [x] Project structure setup
- [ ] Twitter/X implementation
- [ ] Instagram implementation
- [ ] LinkedIn implementation
- [ ] Advanced verification algorithms
- [ ] Command-line interface

## License

MIT
