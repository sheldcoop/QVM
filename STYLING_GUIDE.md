# QVM Dashboard Styling & Animation Guide

This document outlines the design preferences and conventions for the QVM Dashboard to ensure consistency across all future features and applications.

## Color Scheme

### Primary Colors
- **Background**: `#212121` (Dark gray)
- **Text**: `#FFFFFF` (White)
- **Accent/Panel Color**: `#B87333` (Copper/Bronze)
- **Accent Hover**: `#d48c46` (Lighter copper)

### Usage
- Use CSS variables defined in `load_css()` in `app.py`:
  ```css
  :root {
      --background-color: #212121;
      --text-color: #FFFFFF;
      --panel-color: #B87333;
      --panel-hover-color: #d48c46;
  }
  ```
- Always reference these variables rather than hardcoding colors

## Navigation & Button Patterns

### Active/Selected Buttons
- **Primary buttons**: Filled copper background (`--panel-color`) with white text
- **Shape**: Rectangular with rounded corners (`border-radius: 6px`)
- **Usage**: Represents the currently active view/selection

### Inactive Buttons
- **Secondary buttons**: Transparent background with copper border and copper text
- **Shape**: Same rectangular with rounded corners (`border-radius: 6px`)
- **Usage**: Non-active navigation options

### Implementation
Use the `_nav_buttons()` helper function from `app.py`:

```python
def _nav_buttons(options, state_key, default=None, cols_gap="small"):
    """Render a row of primary/secondary buttons for navigation."""
    # Automatically handles session state and renders buttons in columns
    # Returns the selected value
    return selected_value
```

**Example usage:**
```python
selected_view = _nav_buttons(
    ["View A", "View B", "View C"],
    state_key="current_view",
    default="View A",
    cols_gap="small"
)
```

**Why this pattern?**
- `st.pills()` renders as circular buttons (not preferred)
- `st.button(type="primary/secondary", width="stretch")` renders as rectangular (preferred)
- Session state ensures active selection persists across reruns
- `_nav_buttons()` is reusable and keeps code DRY

## Animations & Transitions

### Button Animations

#### Hover State
- **Transition duration**: `0.15s` with `ease` timing
- **Effect**: Color and border-color smoothly change to lighter copper (`--panel-hover-color`)
- **For secondary buttons**: Text color also transitions

#### Click/Active State
- **Transition duration**: `0.1s` with `cubic-bezier(0.175, 0.885, 0.32, 1.275)` (spring-like easing)
- **Effect**: Scale down to `0.95` for tactile feedback
- **Applied to**: `button:active` pseudo-class

#### CSS Implementation
```css
button[data-testid="stBaseButton-primary"],
button[data-testid="stBaseButton-secondary"] {
    border-radius: 6px !important;
    padding: 8px 20px !important;
    transition: transform 0.1s cubic-bezier(0.175, 0.885, 0.32, 1.275), 
                background-color 0.15s ease, 
                border-color 0.15s ease, 
                color 0.15s ease !important;
}
```

### Philosophy
- **Subtle, responsive interactions** — Animations should feel snappy and provide tactile feedback
- **No elaborate animations** — Keep effects minimal and purposeful
- **Always provide visual feedback** — Users should see immediate response to interactions
- **Spring-like easing** — Uses `cubic-bezier(0.175, 0.885, 0.32, 1.275)` for a slight bounce/spring effect

## CSS Selectors & Specificity

### Important Notes
- **DO NOT use** `button[kind="primary"]` — this attribute doesn't exist in Streamlit's DOM
- **DO use** `button[data-testid="stBaseButton-primary"]` and `button[data-testid="stBaseButton-secondary"]`
- **Always use `!important`** — Required to override Streamlit's inline styles
- **Target the actual button element**, not container divs

### Common Selectors
```css
/* Navigation buttons */
button[data-testid="stBaseButton-primary"]
button[data-testid="stBaseButton-secondary"]

/* Download buttons */
.stDownloadButton > button

/* Form submit buttons */
div[data-testid="stFormSubmitButton"] button

/* General buttons */
.stButton button
```

## Session State Management

### Why Session State?
Streamlit reruns the entire script when any widget changes. Using `st.session_state` ensures:
- Active button selection persists across reruns
- No double-click required
- Cleaner state management than relying on `st.pills()` return value

### Pattern
```python
# Initialize state
if "my_selection" not in st.session_state:
    st.session_state["my_selection"] = default_value

# Update via button callback
st.button(
    "Option",
    on_click=lambda: st.session_state.update({"my_selection": "Option"})
)

# Use the value
current_value = st.session_state["my_selection"]
```

## Dark Theme Considerations

The dashboard uses a **dark theme**. Keep these in mind:

1. **Contrast**: Ensure copper accent color has sufficient contrast against dark background
   - Copper on dark gray: ✅ Good contrast (used throughout)
   - White on dark gray: ✅ Good contrast (primary text color)
   - Lighter copper on dark gray: ✅ Acceptable (hover state)

2. **Text Visibility**: 
   - Use white (`#FFFFFF`) or copper (`#B87333`) text
   - Avoid gray text unless it's specifically for secondary/disabled states

3. **Borders**: 
   - Use copper for active/focused states
   - Use lighter copper for hover states
   - Avoid white borders except on hover for download/form buttons

## File Structure

- **Styling**: `qvm_dashboard/assets/styles.css`
- **App Logic**: `qvm_dashboard/app.py`
- **Calculations**: `qvm_dashboard/src/calculations.py`
- **Visualizations**: `qvm_dashboard/src/visuals.py`
- **Data Parsing**: `qvm_dashboard/src/parser.py`

## CSS File Best Practices

1. **Keep styles organized** — Group related styles together with comments
2. **Use variables** — Always reference CSS variables for colors
3. **Document complex selectors** — Add comments explaining why specific selectors are needed
4. **Avoid emotion cache classes** — Streamlit's emotion cache classes (like `.st-emotion-cache-*`) are fragile and can change between versions

Example structure:
```css
/* Theme variables */
:root { ... }

/* Core layout */
.reportview-container { ... }
.sidebar { ... }

/* Typography */
h1, h2, h3 { ... }

/* Buttons - Navigation */
button[data-testid="stBaseButton-primary"] { ... }
button[data-testid="stBaseButton-secondary"] { ... }

/* Buttons - Download/Submit */
.stDownloadButton > button { ... }

/* Animations & Transitions */
@keyframes ... { }
```

## Adding New Features

When adding new features to the QVM Dashboard:

1. ✅ **Use the existing color scheme** — Don't introduce new colors
2. ✅ **Use `_nav_buttons()` for navigation** — Keeps button style consistent
3. ✅ **Add smooth transitions** — 0.15s for color changes, 0.1s for click feedback
4. ✅ **Provide hover states** — Users expect visual feedback
5. ✅ **Document complex interactions** — Add comments explaining state management
6. ✅ **Test dark theme contrast** — Ensure readability on dark background

## Troubleshooting

### Text Not Visible on Buttons
- **Problem**: Text color matches background
- **Solution**: Use copper (`--panel-color`) for secondary buttons or white for primary
- **Debug**: Open DevTools and check computed text color vs background color

### Animations Not Working
- **Problem**: CSS transitions not applying
- **Solution**: Check if `!important` is used (required to override Streamlit styles)
- **Debug**: Verify the selector matches the actual DOM element

### Buttons Still Look Circular
- **Problem**: `border-radius` not being applied
- **Solution**: Ensure `border-radius: 6px !important` is in CSS
- **Debug**: Check DevTools to confirm the CSS rule is applied (not overridden)

### Button Text Disappears on Hover
- **Problem**: Text color changes to background color on hover
- **Solution**: Ensure hover state has a different text color than background
- **Avoid**: Setting `color` to the same value as `background-color` in hover state

## References

- **Streamlit Data Attributes**: Check your browser's DevTools Inspector to find correct `data-testid` values
- **CSS Cubic-Bezier**: https://cubic-bezier.com/ (useful for fine-tuning animations)
- **Color Contrast Checker**: https://webaim.org/resources/contrastchecker/ (verify accessibility)

---

**Last Updated**: April 2026  
**Maintained By**: QVM Development Team
