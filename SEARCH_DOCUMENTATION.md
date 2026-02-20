# Search Functionality Documentation

## Overview
Added comprehensive search functionality for careers, courses, and internships with advanced filtering options. Features a compact single-line search interface with icon-based dropdown filters.

## Features Implemented

### 1. Backend Search Functions (`careers_data.py`)

#### `search_careers(query=None, domain=None, skills=None)`
- **query**: Search in career name, description, and skills
- **domain**: Filter by career domain (Technology, Medicine, etc.)
- **skills**: Filter by required skills

#### `search_courses(query=None, level=None, price_type=None, provider=None)`
- **query**: Search in course name, description, provider, and skills gained
- **level**: Filter by difficulty level (Beginner, Intermediate, All Levels)
- **price_type**: Filter by free/paid courses
- **provider**: Filter by course provider (Coursera, edX, etc.)

#### `search_internships(query=None, domain=None, location=None, company=None)`
- **query**: Search in internship name, description, company, and skills required
- **domain**: Filter by internship domain
- **location**: Filter by location (Remote, Bangalore, etc.)
- **company**: Filter by company name

### 2. API Endpoints (`app.py`)

#### `GET /api/search/careers`
Search careers with query parameters:
- `q`: Search query
- `domain`: Career domain filter
- `skills`: Skills filter (can be multiple)

#### `GET /api/search/courses`
Search courses with query parameters:
- `q`: Search query
- `level`: Course level filter
- `price_type`: Price filter (free/paid)
- `provider`: Provider filter

#### `GET /api/search/internships`
Search internships with query parameters:
- `q`: Search query
- `domain`: Domain filter
- `location`: Location filter
- `company`: Company filter

#### `GET /api/search/filters`
Get available filter options for all search types.

### 3. Frontend Interface (`interests_dashboard.html`)

#### Single-Line Search Interface
- **Search Bar**: Real-time search with 300ms debounce
- **Filter Dropdown**: Icon-based dropdown with tab-specific filters
- **Filter Count Badge**: Shows number of active filters
- **Clear Buttons**: Individual clear for search and filters

#### Filter Panels (Dropdown)
- **Careers**: Domain filter
- **Courses**: Level, Price (Free/Paid), Provider filters
- **Internships**: Domain, Location, Company filters

#### Interactive Features
- Tab-specific filter panels that show/hide based on active tab
- Real-time result updates without page reload
- Result counter with search status
- Loading states and animations
- No results messaging
- Enhanced hover effects and transitions
- Responsive design for mobile and desktop

#### Visual Enhancements
- **Badges**: Color-coded badges for Free/Paid courses and Remote/On-site internships
- **Animations**: Smooth dropdown animations and hover effects
- **Theme Support**: Full dark/light mode compatibility
- **Modern Styling**: Clean, compact interface with proper spacing

## Usage Examples

### Search for free Python courses
1. Go to Courses tab
2. Click filter icon (tune) to open dropdown
3. Enter "python" in search bar
4. Select "Free" from price filter
5. Results update automatically with green "Free" badges

### Find remote technology internships
1. Go to Internships tab
2. Click filter icon
3. Select "Technology" from domain filter
4. Select "Remote" from location filter
5. Results update with purple "Remote" badges

### Search engineering careers
1. Go to Careers tab
2. Enter "engineering" in search bar
3. Or select "Engineering" from domain filter in dropdown
4. Results group by domain automatically

## Technical Implementation

### Search Algorithm
- Case-insensitive partial matching across multiple fields
- Combines multiple filters with AND logic
- Efficient client-side filtering with debounced input

### Performance
- Debounced search input (300ms) to reduce API calls
- Efficient server-side search functions
- Minimal DOM manipulation for results display

### Error Handling
- Graceful degradation on API failures
- User-friendly error messages
- Console logging for debugging
- Safe default values for missing user data

### Tab Functionality
- Fixed tab switching to properly show/hide content
- No automatic search trigger on tab switch
- Proper state management for current tab
- Filter context switching based on active tab

## Data Structure

### Career Fields
- `id`, `name`, `description`, `domain`, `skills`, `courses`, `internships`

### Course Fields
- `id`, `name`, `provider`, `level`, `duration`, `price`, `description`, `skills_gained`, `related_careers`, `link`

### Internship Fields
- `id`, `name`, `domain`, `company`, `duration`, `location`, `skills_required`, `eligibility`, `description`, `how_to_apply`

## Fixes Applied

### 1. Tab Switching Issues
- Fixed JavaScript tab switching logic to properly show/hide content
- Added proper state management for current tab
- Prevented automatic search on tab switch

### 2. Detail Page Routing
- Fixed `get_user_data()` function to return empty dict instead of None
- Ensured all detail pages (/course/, /internship/, /career/) work correctly
- Added proper error handling for missing items

### 3. Search and Filter Integration
- Ensured search works across all tabs without interference
- Fixed filter dropdown to show context-specific options
- Added proper event handling for filter changes

## Compatibility
- Maintains all existing functionality
- No breaking changes to current features
- Responsive design for mobile and desktop
- Compatible with existing theme system
- Works with all modern browsers

## Recent Updates
- **Redesigned Interface**: Compact single-line search with icon dropdown
- **Enhanced Styling**: Better visual appeal with animations and badges
- **Fixed Routing**: Course and internship detail pages now work correctly
- **Improved UX**: Better tab switching and filter management
