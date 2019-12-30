
$(document).ready(function () {
	$("input[data-provide='slider']").on('slideStop',function(ev){
		var ctrl = $(ev.target).attr('id')
		var val = $(ev.target).val()
		if (ctrl.substr(0,12)=="ALSA_VOLUME_") ctrl = ctrl.substr(12)
		if (ctrl.substr(0,26)=="ZYNTHIAN_CONTROLLER_VALUE_") ctrl = ctrl.substr(26)
		
		console.log("Audio Mixer Set: " + ctrl + " = " + val)

		//Call Audio Mixer Handler
		$.post("hw-audio-mixer/" + ctrl + "/" + val,
			null,
			function(data, status) {
				if (status=="success") {
					if (data && "errors" in data) {
						console.log("Audio Mixer Error: " + data["errors"])
					}
				} else {
					console.log("Audio Mixer Response: " + status)
				}
			}
		)

	});
});
