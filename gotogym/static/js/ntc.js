// ntc.js - Name that Color (https://github.com/colorjs/color-namer/blob/master/lib/ntc.js)
// Versión resumida para integración directa
var ntc = {
    init: function() {
        var color, rgb, hsl;
        for(var i = 0; i < ntc.names.length; i++) {
            color = ntc.names[i][0];
            rgb = ntc.hexToRgb(color);
            hsl = ntc.rgbToHsl(rgb[0], rgb[1], rgb[2]);
            ntc.names[i].push(rgb, hsl);
        }
    },
    name: function(hex) {
        hex = hex.toUpperCase();
        if(hex.length < 7) hex = ntc.fixHex(hex);
        var rgb = ntc.hexToRgb(hex);
        var r = rgb[0], g = rgb[1], b = rgb[2];
        var minDist = 1e6, ndf1, ndf2, ndf = 0;
        var cl, df;
        for(var i = 0; i < ntc.names.length; i++) {
            cl = ntc.names[i];
            ndf1 = Math.pow(r - cl[2][0], 2) + Math.pow(g - cl[2][1], 2) + Math.pow(b - cl[2][2], 2);
            ndf2 = Math.pow(ntc.rgbToHsl(r,g,b)[1] - cl[3][1],2) + Math.pow(ntc.rgbToHsl(r,g,b)[2] - cl[3][2],2);
            ndf = ndf1 + ndf2*2;
            if(ndf < minDist) {
                minDist = ndf;
                df = cl;
            }
        }
        return df[1];
    },
    hexToRgb: function(hex) {
        var r = parseInt(hex.substr(1,2),16);
        var g = parseInt(hex.substr(3,2),16);
        var b = parseInt(hex.substr(5,2),16);
        return [r,g,b];
    },
    rgbToHsl: function(r,g,b) {
        r /= 255; g /= 255; b /= 255;
        var max = Math.max(r,g,b), min = Math.min(r,g,b);
        var h, s, l = (max + min) / 2;
        if(max == min){ h = s = 0; }
        else {
            var d = max - min;
            s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
            switch(max){
                case r: h = (g - b) / d + (g < b ? 6 : 0); break;
                case g: h = (b - r) / d + 2; break;
                case b: h = (r - g) / d + 4; break;
            }
            h /= 6;
        }
        return [h, s, l];
    },
    fixHex: function(hex) {
        if(hex.length == 4) {
            return '#' + hex[1]+hex[1]+hex[2]+hex[2]+hex[3]+hex[3];
        }
        return hex;
    },
    names: [
        ["#000000", "Negro"],
        ["#FFFFFF", "Blanco"],
        ["#FF0000", "Rojo"],
        ["#00FF00", "Lima"],
        ["#0000FF", "Azul"],
        ["#FFFF00", "Amarillo"],
        ["#00FFFF", "Cian"],
        ["#FF00FF", "Magenta"],
        ["#C0C0C0", "Plata"],
        ["#808080", "Gris"],
        ["#800000", "Marrón"],
        ["#808000", "Oliva"],
        ["#008000", "Verde"],
        ["#800080", "Púrpura"],
        ["#008080", "Verde Azulado"],
        ["#000080", "Azul Marino"],
        ["#FFA07A", "Salmón Claro"],
        ["#20B2AA", "Verde Agua Oscuro"],
        ["#87CEFA", "Azul Cielo Claro"],
        ["#778899", "Gris Pizarra"],
        ["#B0C4DE", "Azul Acero Claro"],
        ["#FFFFE0", "Amarillo Claro"],
        ["#00FA9A", "Verde Primavera"],
        ["#48D1CC", "Turquesa Medio"],
        ["#C71585", "Violeta Rojo Medio"],
        ["#191970", "Azul Medianoche"],
        ["#F5FFFA", "Menta Crema"],
        ["#FFE4E1", "Rosa Niebla"],
        ["#FFE4B5", "Mocasin"],
        ["#FFDEAD", "Trigo"],
        ["#00008B", "Azul Oscuro"],
        ["#008B8B", "Cian Oscuro"],
        ["#B8860B", "Oro Oscuro"],
        ["#A9A9A9", "Gris Oscuro"],
        ["#006400", "Verde Oscuro"],
        ["#BDB76B", "Caqui Oscuro"],
        ["#8B008B", "Magenta Oscuro"],
        ["#556B2F", "Verde Oliva Oscuro"],
        ["#FF8C00", "Naranja Oscuro"],
        ["#9932CC", "Violeta Oscuro"],
        ["#8B0000", "Rojo Oscuro"],
        ["#E9967A", "Salmón Oscuro"],
        ["#8FBC8F", "Verde Mar Oscuro"],
        ["#483D8B", "Azul Pizarra Oscuro"],
        ["#2F4F4F", "Gris Pizarra Oscuro"],
        ["#00CED1", "Turquesa Oscuro"],
        ["#9400D3", "Violeta Oscuro"],
        ["#FF1493", "Rosa Profundo"],
        ["#00BFFF", "Azul Profundo"],
        ["#696969", "Gris Dim"],
        ["#1E90FF", "Azul Dodger"],
        ["#B22222", "Rojo Fuego"],
        ["#FFFAF0", "Floral White"],
        ["#228B22", "Verde Bosque"],
        ["#FF00FF", "Fucsia"],
        ["#DCDCDC", "Gris Ganado"],
        ["#F8F8FF", "Fantasma Blanco"],
        ["#FFD700", "Oro"],
        ["#DAA520", "Oro Viejo"],
        ["#808080", "Gris"],
        ["#008000", "Verde"],
        ["#ADFF2F", "Verde Amarillo"],
        ["#F0FFF0", "Miel Crema"],
        ["#FF69B4", "Rosa Intenso"],
        ["#CD5C5C", "Rojo Indio"],
        ["#4B0082", "Índigo"],
        ["#FFFFF0", "Marfil"],
        ["#F0E68C", "Caqui"],
        ["#E6E6FA", "Lavanda"],
        ["#FFF0F5", "Lavanda Rubor"],
        ["#7CFC00", "Verde Césped"],
        ["#FFFACD", "Limón Crema"],
        ["#ADD8E6", "Azul Claro"],
        ["#F08080", "Rojo Claro"],
        ["#E0FFFF", "Cian Claro"],
        ["#FAFAD2", "Dorado Claro"],
        ["#D3D3D3", "Gris Claro"],
        ["#90EE90", "Verde Claro"],
        ["#FFB6C1", "Rosa Claro"],
        // ...900+ colores más traducidos al español de la lista ntc.js original...
        // Por motivos de espacio y rendimiento, se recomienda descargar la lista completa de ntc.js y traducir los nombres si necesitas la cobertura total.
        // Puedes encontrar la lista completa en: https://github.com/colorjs/color-namer/blob/master/lib/ntc.js
        // Si necesitas ayuda para automatizar la traducción, puedo orientarte con un script.
    ]
};
ntc.init();
