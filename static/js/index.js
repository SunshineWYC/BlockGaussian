window.HELP_IMPROVE_VIDEOJS = false;


$(document).ready(function() {
    // Check for click events on the navbar burger icon

    var options = {
			slidesToScroll: 1,
			slidesToShow: 1,
			loop: true,
			infinite: true,
			autoplay: true,
			autoplaySpeed: 5000,
    }

		// Initialize all div with carousel class
    var carousels = bulmaCarousel.attach('.carousel', options);
	
    bulmaSlider.attach();
})


document.addEventListener("DOMContentLoaded", (event) => {
    var b = document.querySelectorAll('.b-dics');
    b.forEach(element =>
        new Dics({
            container: element,
            textPosition: 'bottom',
            arrayBackgroundColorText: ['#000000', '#000000', '#000000'],
            arrayColorText: ['#FFFFFF', '#FFFFFF', '#FFFFFF'],
            linesColor: '#ffffff'
        })
    );

});
