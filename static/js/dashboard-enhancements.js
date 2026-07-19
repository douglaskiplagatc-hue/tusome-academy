$(document).ready(function() {
    // Function to decide if a table should be enhanced with DataTables
    function shouldEnhanceTable(table) {
        // 1. Skip tables with class 'no-enhance' (opt-out)
        if ($(table).hasClass('no-enhance')) return false;

        // 2. Skip tables with fewer than 10 rows (small lookup tables)
        const rowCount = $(table).find('tbody tr').length;
        if (rowCount < 10) return false;

        // 3. Check if table has <thead> and at least 3 columns
        const columnCount = $(table).find('thead th').length;
        if (columnCount < 3) return false;

        // 4. Look for keywords in the first two header cells
        const headers = $(table).find('thead th').map((i, th) => $(th).text().toLowerCase()).get();
        const keywords = ['name', 'admission', 'student', 'grade', 'marks', 'subject', 'class', 'average', 'total', 'score', 'attendance'];
        const hasKeyword = headers.some(h => keywords.some(kw => h.includes(kw)));
        if (!hasKeyword) return false;

        // 5. If table is inside a container with class 'table-container' or 'data-grid', enhance it
        if ($(table).closest('.table-container, .data-grid, .data-table-container').length) return true;

        // 6. Finally, if it passes row count and column count and has a keyword, enhance it
        return true;
    }

    // Apply DataTables to qualifying tables
    $('table').each(function() {
        const table = this;
        if (shouldEnhanceTable(table)) {
            // Destroy existing DataTable if any
            if ($.fn.DataTable.isDataTable(table)) {
                $(table).DataTable().destroy();
            }
            $(table).DataTable({
                responsive: true,
                pageLength: 25,
                lengthMenu: [[10, 25, 50, -1], [10, 25, 50, "All"]],
                language: {
                    search: "Filter:",
                    lengthMenu: "Show _MENU_ entries",
                    info: "Showing _START_ to _END_ of _TOTAL_ entries",
                    paginate: { first: "First", last: "Last", next: "→", previous: "←" }
                },
                dom: '<"row"<"col-sm-6"l><"col-sm-6"f>>' +
                     '<"row"<"col-sm-12"tr>>' +
                     '<"row"<"col-sm-5"i><"col-sm-7"p>>'
            });
        }
    });

    // Charts (unchanged)
    $('canvas.auto-chart').each(function() {
        const ctx = this.getContext('2d');
        const chartData = $(this).data('chart');
        if (chartData) new Chart(ctx, chartData);
    });
});

// Helper function to create a chart (for dynamic content)
function createChart(canvasId, type, labels, data, colors) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: type,
        data: {
            labels: labels,
            datasets: [{
                label: 'Dataset',
                data: data,
                backgroundColor: colors || ['#006B3F', '#0047AB', '#FCD116', '#BB0000', '#00a86b'],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { position: 'top' },
                tooltip: { enabled: true }
            }
        }
    });
}

// Function to colour-code table rows based on a value (e.g., grade)
function applyRowColouring(selector, valueAttr, colourMap) {
    $(selector).each(function() {
        const value = $(this).data(valueAttr);
        if (value && colourMap[value]) {
            $(this).css('background-color', colourMap[value]);
        }
    });
}
